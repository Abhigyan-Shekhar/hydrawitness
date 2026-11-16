"""Advisory evidence assessment backed by HydraDB. Synthetic/local artifacts only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
import time
from collections import deque
from contextlib import contextmanager
from .proof import query

REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_./-]{0,199}$')
COMMIT = re.compile(r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')
DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')
GITHUB_ACTIONS_VERIFICATION = 'github_actions_rest'

def valid_subject(subject):
    if not isinstance(subject, dict) or set(subject) != {'kind', 'value'}:
        return False
    value = subject['value']
    if not isinstance(value, str): return False
    if subject['kind'] == 'git_commit': return bool(COMMIT.fullmatch(value))
    if subject['kind'] == 'artifact_digest': return bool(DIGEST.fullmatch(value))
    return False

def identity(scope, kind, name):
    return int.from_bytes(hashlib.sha256(f'{scope}\0{kind}\0{name}'.encode()).digest()[:7], 'big')

class Registry:
    """Index only regular JSON files in a trusted directory; references are keys, never paths."""
    def __init__(self, directory):
        self.items = {}
        root = Path(directory).resolve()
        for path in sorted(root.glob('*.json')):
            if path.is_symlink() or not path.is_file():
                continue
            item = json.loads(path.read_text())
            if not isinstance(item, dict) or 'external_id' not in item or 'type' not in item:
                continue
            validate(item)
            key = item['external_id']
            if key in self.items:
                raise ValueError(f'duplicate artifact identity: {key}')
            self.items[key] = item
    def get(self, ref):
        return self.items.get(ref)

def validate(a):
    if not isinstance(a.get('external_id'), str) or not REF.fullmatch(a['external_id']) or '..' in a['external_id']:
        raise ValueError('invalid artifact identifier')
    if a.get('type') not in ('report','ci','security_scan','observation'):
        raise ValueError('invalid artifact type')
    if not isinstance(a.get('references', []), list) or not isinstance(a.get('required', []), list):
        raise ValueError('references must be lists')
    for ref in a.get('references', []) + a.get('required', []):
        if not isinstance(ref, str) or not REF.fullmatch(ref) or '..' in ref:
            raise ValueError('invalid reference')
    if len(set(a.get('references', []))) != len(a.get('references', [])) or len(set(a.get('required', []))) != len(a.get('required', [])):
        raise ValueError('duplicate references')
    if a.get('root_verified') and a.get('references'):
        raise ValueError('a root cannot declare upstream references')
    if a.get('outcome') not in (None, 'passed', 'failed', 'skipped', 'unknown'):
        raise ValueError('invalid outcome')
    if a.get('type') == 'security_scan' and a.get('subject') is not None and not valid_subject(a['subject']):
        raise ValueError('invalid scan subject')
    if not isinstance(a.get('observed_at'), str):
        raise ValueError('observed_at required')
    try:
        observed = datetime.fromisoformat(a['observed_at'].replace('Z', '+00:00'))
        if observed.tzinfo is None: raise ValueError('timezone required')
    except ValueError as exc:
        raise ValueError('invalid observed_at') from exc

class Witness:
    def __init__(self, scope, registry, *, max_depth=8, now=None):
        self.scope, self.registry, self.max_depth = scope, registry, max_depth
        self.now = now or datetime.now(timezone.utc)
        self.queries = 0
        self.query_log = []
        self.read_only = False
    def q(self, cypher, params=None):
        if self.read_only and not cypher.lstrip().upper().startswith('MATCH '):
            raise RuntimeError('read-only evaluation rejected non-MATCH query')
        if self.read_only and re.search(r'\b(CREATE|MERGE|SET|DELETE|REMOVE|UNWIND|CALL)\b', cypher, re.IGNORECASE):
            raise RuntimeError('read-only evaluation rejected mutation')
        self.queries += 1
        started = time.perf_counter()
        try:
            return query(cypher, params)
        finally:
            self.query_log.append({'cypher':cypher, 'duration_ms':(time.perf_counter()-started)*1000})
    @contextmanager
    def readonly(self):
        previous = self.read_only
        self.read_only = True
        try: yield
        finally: self.read_only = previous
    def nid(self, kind, key): return identity(self.scope, kind, key)
    def node(self, label, key, payload):
        node_id = self.nid(label, key)
        rows = self.q(f'MATCH (n:{label} {{id: $id}}) RETURN n.payload AS payload', {'id':node_id})
        data = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        if rows:
            if rows[0]['payload'] != data:
                raise ValueError(f'immutable {label} identity conflict: {key}')
            return node_id, False
        self.q(f'CREATE (n:{label} {{id: $id, payload: $payload}})', {'id':node_id, 'payload':data})
        return node_id, True
    def edge(self, a_label, a, kind, b_label, b):
        args = {'a':a,'b':b}
        match = f'MATCH (a:{a_label} {{id: $a}})-[:{kind}]->(b:{b_label} {{id: $b}}) RETURN b.id AS id'
        if self.q(match, args): return False
        self.q(f'MERGE (a:{a_label} {{id: $a}})-[:{kind}]->(b:{b_label} {{id: $b}})', args)
        return True
    def source(self, ref):
        rows = self.q('MATCH (s:Source {id: $id}) RETURN s.payload AS payload', {'id':self.nid('Source',ref)})
        if not rows: return None
        data = json.loads(rows[0]['payload'])
        if data.get('external_id') != ref: raise ValueError('source identity mismatch')
        return data
    def seed_claim(self, claim_id, source_refs, *, subject=None):
        if subject is not None and not valid_subject(subject): raise ValueError('invalid release subject')
        payload={'claim_id':claim_id}
        if subject is not None: payload['subject']=subject
        self.node('Claim', claim_id, payload)
        for ref in source_refs:
            artifact = self.registry.get(ref)
            if not artifact: raise ValueError(f'missing initial artifact {ref}')
            self.node('Source', ref, artifact)
            self.edge('Source',self.nid('Source',ref),'SUPPORTS','Claim',self.nid('Claim',claim_id))
    def claim_subject(self, claim_id):
        rows=self.q('MATCH (c:Claim {id: $id}) RETURN c.payload AS payload', {'id':self.nid('Claim',claim_id)})
        if not rows: raise ValueError('unknown claim')
        claim=json.loads(rows[0]['payload'])
        if claim.get('claim_id') != claim_id: raise ValueError('claim identity mismatch')
        return claim.get('subject')
    def ingest_workflow_evidence(self, claim_id, subject, artifacts):
        """Attach validated GitHub run observations to an immutable commit-bound claim."""
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError('claim identifier is required')
        if not valid_subject(subject) or subject['kind'] != 'git_commit':
            raise ValueError('workflow evidence requires an exact Git commit subject')
        observations = {}
        for artifact in artifacts:
            if (not isinstance(artifact, dict) or artifact.get('type') != 'ci'
                    or artifact.get('verification_method') != GITHUB_ACTIONS_VERIFICATION
                    or artifact.get('root_verified') is not False
                    or artifact.get('references') or artifact.get('required')):
                raise ValueError('invalid GitHub Actions evidence')
            validate(artifact)
            if artifact.get('subject') != subject:
                raise ValueError('workflow evidence subject does not match the claim commit')
            reference = artifact['external_id']
            if reference in observations and observations[reference] != artifact:
                raise ValueError(f'conflicting workflow evidence: {reference}')
            observations[reference] = artifact

        counts = {'sources_ingested': 0, 'edges_added': 0}
        if observations:
            claim_node, _ = self.node('Claim', claim_id, {'claim_id': claim_id, 'subject': subject})
            for reference, artifact in sorted(observations.items()):
                source_node, created = self.node('Source', reference, artifact)
                counts['sources_ingested'] += int(created)
                counts['edges_added'] += int(self.edge('Source', source_node, 'CI_EVIDENCE_FOR', 'Claim', claim_node))
        return counts
    def workflow_evidence(self, claim_id):
        """Read CI observations linked to the claim and pinned to its commit."""
        rows = self.q(
            'MATCH (s:Source)-[:CI_EVIDENCE_FOR]->(c:Claim {id: $id}) '
            'RETURN DISTINCT s.id AS id, s.payload AS payload, c.payload AS claim',
            {'id': self.nid('Claim', claim_id)},
        )
        observations = []
        for row in rows:
            claim = json.loads(row['claim'])
            artifact = json.loads(row['payload'])
            subject, reference = claim.get('subject'), artifact.get('external_id')
            if (claim.get('claim_id') == claim_id and valid_subject(subject) and subject['kind'] == 'git_commit'
                    and artifact.get('subject') == subject and artifact.get('type') == 'ci'
                    and artifact.get('verification_method') == GITHUB_ACTIONS_VERIFICATION
                    and isinstance(reference, str) and self.nid('Source', reference) == row['id']):
                observations.append(artifact)
        return sorted(observations, key=lambda artifact: artifact['external_id'])
    def attached(self, claim_id):
        cid=self.nid('Claim',claim_id)
        if not self.q('MATCH (c:Claim {id: $id}) RETURN c.id AS id', {'id':cid}): raise ValueError('unknown claim')
        rows=self.q('MATCH (s:Source)-[:SUPPORTS]->(c:Claim {id: $id}) RETURN DISTINCT s.payload AS payload', {'id':cid})
        return [json.loads(x['payload']) for x in rows]
    def neighbors(self, ref, relationship):
        rows=self.q(f'MATCH (s:Source {{id: $id}})-[:{relationship}]->(p:Source) RETURN DISTINCT p.payload AS payload', {'id':self.nid('Source',ref)})
        return [json.loads(x['payload']) for x in rows]
    def reverse_sources(self, ref, relationship):
        if relationship not in ('REQUIRES', 'DERIVED_FROM'): raise ValueError('invalid relationship')
        rows=self.q(f'MATCH (s:Source)-[:{relationship}]->(p:Source {{id: $id}}) RETURN DISTINCT s.id AS id, s.payload AS payload', {'id':self.nid('Source',ref)})
        result=[]
        for row in rows:
            data=json.loads(row['payload'])
            if isinstance(data,dict) and isinstance(data.get('external_id'),str) and row['id']==self.nid('Source',data['external_id']):
                result.append(data)
        return result
    def supporting_claims(self, ref):
        rows=self.q('MATCH (s:Source {id: $id})-[:SUPPORTS]->(c:Claim) RETURN DISTINCT c.id AS id, c.payload AS payload', {'id':self.nid('Source',ref)})
        result=[]
        for row in rows:
            data=json.loads(row['payload'])
            if isinstance(data,dict) and isinstance(data.get('claim_id'),str) and row['id']==self.nid('Claim',data['claim_id']):
                result.append(data)
        return result
    def scan_impact(self, scan_id):
        """Find claims whose declared evidence paths include this scan, without mutation."""
        if not isinstance(scan_id, str) or not REF.fullmatch(scan_id) or '..' in scan_id:
            raise ValueError('invalid scan identifier')
        with self.readonly():
            scan=self.source(scan_id)
            if not scan or scan.get('type')!='security_scan': raise ValueError('unknown security scan')
            subject=scan.get('subject')
            result={'scan_id':scan_id,'subject':subject if valid_subject(subject) else None,'impacted_claims':[]}
            if not valid_subject(subject) or self.max_depth<=0: return result
            queue=deque()
            seen=set()
            for source in sorted(self.reverse_sources(scan_id,'REQUIRES'),key=lambda x:x['external_id']):
                ref=source['external_id']
                if not isinstance(source.get('required',[]),list) or scan_id not in source.get('required',[]): continue
                if ref in seen: continue
                seen.add(ref)
                queue.append((ref,[{'from':ref,'to':scan_id,'type':'REQUIRES'}],0))
            claims={}
            while queue:
                ref,path,depth=queue.popleft()
                for claim in sorted(self.supporting_claims(ref),key=lambda x:x['claim_id']):
                    claim_id=claim['claim_id']
                    if claim_id in claims or not valid_subject(claim.get('subject')) or claim['subject']!=subject: continue
                    claims[claim_id]={'claim_id':claim_id,'status':'REASSESSMENT_REQUIRED','path':[{'from':ref,'to':claim_id,'type':'SUPPORTS'}]+path}
                if depth+1>=self.max_depth: continue
                for source in sorted(self.reverse_sources(ref,'DERIVED_FROM'),key=lambda x:x['external_id']):
                    child=source['external_id']
                    if not isinstance(source.get('references',[]),list) or ref not in source.get('references',[]): continue
                    if child in seen: continue
                    seen.add(child)
                    queue.append((child,[{'from':child,'to':ref,'type':'DERIVED_FROM'}]+path,depth+1))
            result['impacted_claims']=[claims[key] for key in sorted(claims)]
            return result
    def assess(self, claim_id, policy):
        """Trace verified lineage; checks are valid only when linked to evidence."""
        if isinstance(policy, str):
            policies = json.loads((Path(__file__).resolve().parent.parent / 'datasets/policies.json').read_text())
            if policy not in policies: raise ValueError('unknown policy')
            policy = policies[policy]
        if not isinstance(policy.get('id'),str) or policy.get('min_roots',1)<1: raise ValueError('invalid policy')
        require_scan = policy.get('require_security_scan')
        roots, gaps, states, scans = set(), [], {}, []
        def gap(kind, ref, **extra):
            item={'kind':kind, 'reference':ref, **extra}
            if item not in gaps: gaps.append(item)
        subject=self.claim_subject(claim_id)
        subject_valid=valid_subject(subject)
        if require_scan:
            if subject is None: gap('missing_release_subject',claim_id)
            elif not subject_valid: gap('invalid_release_subject',claim_id)
        def visit(a, path):
            ref=a['external_id']
            if ref in path:
                gap('cycle', ref); states[ref]='INVALID_LINEAGE'; return 'INVALID_LINEAGE'
            if len(path)>=self.max_depth:
                gap('depth_limit', ref); states[ref]='UNRESOLVED_LINEAGE'; return 'UNRESOLVED_LINEAGE'
            observed=datetime.fromisoformat(a['observed_at'].replace('Z','+00:00'))
            stale = observed > self.now or (self.now-observed).total_seconds() > policy.get('max_age_days',365)*86400
            if stale: gap('stale_evidence',ref)
            parents={x['external_id']:x for x in self.neighbors(ref,'DERIVED_FROM')}
            required={x['external_id']:x for x in self.neighbors(ref,'REQUIRES')}
            for need in a.get('required',[]):
                if need not in required: gap('missing_required_artifact',need, from_source=ref)
            for obj in required.values():
                if obj['external_id'] not in a.get('required',[]):
                    gap('invalid_relationship',obj['external_id'],from_source=ref); continue
                if obj.get('type')!='security_scan':
                    gap('invalid_relationship',obj['external_id'],from_source=ref); continue
                if obj.get('root_verified') is not True or obj.get('references'):
                    gap('incomplete_provenance',obj['external_id']); continue
                scans.append(obj)
            for expected in a.get('references',[]):
                if expected not in parents: gap('missing_reference',expected,from_source=ref)
            if set(parents)-set(a.get('references',[])):
                gap('invalid_relationship',ref); states[ref]='INVALID_LINEAGE'; return 'INVALID_LINEAGE'
            child_states=[visit(p,path+(ref,)) for p in parents.values()]
            if 'INVALID_LINEAGE' in child_states: state='INVALID_LINEAGE'
            elif stale or len(parents)!=len(a.get('references',[])) or 'UNRESOLVED_LINEAGE' in child_states: state='UNRESOLVED_LINEAGE'
            elif not parents:
                state='VERIFIED_ROOT' if a.get('root_verified') is True else 'UNRESOLVED_LINEAGE'
                if state=='VERIFIED_ROOT': roots.add(ref)
                else: gap('incomplete_provenance',ref)
            else: state='VERIFIED_LINEAGE'  # paths terminate at explicitly verified roots
            states[ref]=state
            return state
        sources=self.attached(claim_id)
        for a in sources:
            prior_roots = set(roots)
            state = visit(a,())
            if state not in ('VERIFIED_ROOT','VERIFIED_LINEAGE'):
                roots.intersection_update(prior_roots)
        current_scans=[]
        for scan in scans:
            observed=datetime.fromisoformat(scan['observed_at'].replace('Z','+00:00'))
            current=observed<=self.now and (self.now-observed).total_seconds()<=policy.get('max_age_days',365)*86400
            if not current: gap('stale_evidence',scan['external_id'])
            if require_scan:
                scan_subject=scan.get('subject')
                if scan_subject is None:
                    gap('missing_scan_subject',scan['external_id']); continue
                if not valid_subject(scan_subject):
                    gap('invalid_scan_subject',scan['external_id']); continue
                if not subject_valid: continue
                if scan_subject != subject:
                    gap('scan_subject_mismatch',scan['external_id'],scan_subject=scan_subject); continue
            if current:
                current_scans.append(scan)
                if scan.get('outcome') in ('skipped','failed'):
                    gap('contradictory_outcome',scan['external_id'],outcome=scan['outcome'])
                elif scan.get('outcome') != 'passed' and require_scan:
                    gap('unknown_verification_outcome',scan['external_id'])
        failed=any(x.get('outcome') in ('skipped','failed') for x in current_scans)
        passed=bool(current_scans) and all(x.get('outcome')=='passed' for x in current_scans)
        if require_scan and not current_scans: gap('missing_mandatory_verification','security_scan')
        unresolved=any(g['kind'] not in ('contradictory_outcome',) for g in gaps)
        if failed and require_scan: verdict='BLOCK'; explanation='A linked required security scan for this release was skipped or failed.'
        elif failed or unresolved or len(roots)<policy.get('min_roots',1) or (require_scan and not passed):
            verdict='REVIEW_REQUIRED'; explanation='Evidence, independent origins, or required verification is incomplete.'
        else: verdict='APPROVE'; explanation='The policy requirements are satisfied by current evidence.'
        return {'claim_id':claim_id,'subject':subject if subject_valid else None,'policy_id':policy['id'],'verdict':verdict,'explanation':explanation,'supporting_documents':len(sources),'verified_roots':sorted(roots),'lineage_states':states,'gaps':gaps}
    def resolve(self, gaps):
        sources,edges=[],0
        for g in gaps:
            if g['kind'] not in ('missing_reference','missing_required_artifact'): continue
            ref=g['reference']; parent=g['from_source']; original=self.source(parent)
            key='references' if g['kind']=='missing_reference' else 'required'
            if not original or ref not in original.get(key,[]): raise ValueError('gap is not supported by source metadata')
            artifact=self.registry.get(ref)
            if artifact is None: continue
            validate(artifact)
            if artifact['external_id'] != ref: raise ValueError('artifact identity mismatch')
            if key=='required' and artifact['type']!='security_scan': raise ValueError('required verification type mismatch')
            _,created=self.node('Source',ref,artifact)
            edges+=int(self.edge('Source',self.nid('Source',parent),'DERIVED_FROM' if key=='references' else 'REQUIRES','Source',self.nid('Source',ref)))
            if created: sources.append(ref)
        return sources,edges
    def improve(self, claim_id, policy, max_iterations=5):
        if max_iterations<0: raise ValueError('invalid iteration budget')
        start=self.queries; before=self.assess(claim_id,policy); history=[]; current=before
        for iteration in range(1,max_iterations+1):
            sources,edges=self.resolve(current['gaps'])
            if not sources and not edges: break
            after=self.assess(claim_id,policy)
            item={'claim_id':claim_id,'iteration':iteration,'original_verdict':current['verdict'],'updated_verdict':after['verdict'],'discovered_gaps':current['gaps'],'sources_ingested':sources,'edges_added':edges,'verified_roots':after['verified_roots'],'remaining_uncertainty':after['gaps'],'decision_changed':current['verdict']!=after['verdict']}
            run_id=str(uuid.uuid4()); self.node('Improvement',run_id,item)
            self.edge('Improvement',self.nid('Improvement',run_id),'FOR_CLAIM','Claim',self.nid('Claim',claim_id))
            history.append(item); current=after
        return {'before':before,'after':current,'history':history,'query_count':self.queries-start,'sources_ingested':sum(len(x['sources_ingested']) for x in history),'edges_added':sum(x['edges_added'] for x in history)}
