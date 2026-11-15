"""Small reproducible proof using a live HydraDB, not a graph substitute."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid

URL = os.getenv('HYDRA_URL', 'http://127.0.0.1:18443')
TOKEN = os.getenv('HYDRA_TOKEN', 'local-development-token-32-bytes')

def query(cypher, parameters=None):
    body = json.dumps({'cell_id':'cell-0', 'query_id':str(uuid.uuid4()), 'query':cypher, 'parameters':parameters or {}}).encode()
    req = urllib.request.Request(URL + '/v1/graphs/default/query', data=body, headers={'Authorization':'Bearer '+TOKEN, 'X-Graph-Namespace':'default', 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        exc.close()
        raise RuntimeError(f'HydraDB query failed: {exc.code}: {detail}') from exc
    if result.get('next_cursor'):
        raise RuntimeError('Unexpected pagination; refusing to use incomplete graph results')
    return [{key: cell.get('value') for key, cell in zip(result['columns'], row)} for row in result['rows']]

def seed():
    for node_id in (71001,71002,71003,71004):
        if not query('MATCH (n:Source {id: $id}) RETURN n.id AS id', {'id':node_id}):
            query('CREATE (n:Source {id: $id})', {'id':node_id})
    if not query('MATCH (n:Claim {id: 71010}) RETURN n.id AS id'):
        query('CREATE (n:Claim {id: 71010})')
    for source, parent in ((71001,71004),(71002,71001),(71003,71002)):
        query('MERGE (a:Source {id: $a})-[:DERIVED_FROM]->(b:Source {id: $b})', {'a':source,'b':parent})
    for source in (71001,71002,71003):
        query('MERGE (a:Source {id: $a})-[:SUPPORTS]->(b:Claim {id: 71010})', {'a':source})

def roots(source):
    # Walk adjacency from HydraDB; a missing/too-deep chain is never a root.
    stack = [(source, (source,))]; found = set(); errors = []
    while stack:
        current, path = stack.pop()
        parents = query('MATCH (s:Source {id: $id})-[:DERIVED_FROM]->(p:Source) RETURN DISTINCT p.id AS id', {'id':current})
        if not parents:
            found.add(current)
        for row in parents:
            parent = row['id']
            if parent in path: errors.append('cycle'); continue
            if len(path) >= 6: errors.append('depth_limit'); continue
            stack.append((parent, path + (parent,)))
    return sorted(found), sorted(set(errors))

def assess():
    evidence = query('MATCH (s:Source)-[:SUPPORTS]->(c:Claim {id: 71010}) RETURN DISTINCT s.id AS id')
    all_roots, issues = set(), []
    for row in evidence:
        r, e = roots(row['id']); all_roots.update(r); issues.extend(e)
    scan = query('MATCH (s:Source {id: 71005})-[:CONTRADICTS]->(c:Claim {id: 71010}) RETURN s.outcome AS outcome')
    skipped = any(row['outcome'] == 'skipped' for row in scan)
    return {'supporting_documents':len(evidence), 'roots':sorted(all_roots), 'issues':sorted(set(issues)), 'verdict':'BLOCK' if skipped else 'REVIEW_REQUIRED', 'explanation':'Required security scan was skipped.' if skipped else 'The required security scan artifact has not been verified.'}

def repair():
    # This explicit fixture is the sole targeted artifact: scan 71005 reports skipped.
    artifact = json.loads((Path(__file__).resolve().parent.parent / 'datasets/evidence/security-scan-71005.json').read_text())
    if artifact['id'] != 71005 or artifact['reference'] != 'run-927/security-scan':
        raise ValueError('Unexpected scan artifact identity or reference')
    query('MERGE (s:Source {id: $id, content: $content, outcome: $outcome, external_id: $external_id})-[:CONTRADICTS]->(c:Claim {id: 71010})', artifact)

def main():
    seed()
    before = assess()
    repair()
    after = assess()
    print(json.dumps({'before':before,'after':after, 'discovered_artifact': 'security-scan-71005: skipped', 'note':'Synthetic fixture; advisory only. On repeated runs the repair already exists.'}, indent=2))

if __name__ == '__main__': main()
