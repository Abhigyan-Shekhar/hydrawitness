"""Compare preserved full run with a document-only, reference-resolving ablation."""
import json
from pathlib import Path
import uuid
from hydrawitness.engine import Registry, Witness
from evals.run import DATA, NOW, evaluate, validate_dataset

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'evals/ablation-results'

class MetadataWitness(Witness):
    """Read referenced artifacts by key; derive lineage at query time, never read graph provenance edges."""
    def neighbors(self, ref, relationship):
        source=self.source(ref)
        if source is None: raise ValueError('missing attached source')
        field={'DERIVED_FROM':'references','REQUIRES':'required'}[relationship]
        result=[]
        for key in source.get(field,[]):
            item=self.source(key)
            if item is not None:
                result.append(item)
        return result

def main():
    manifest,learning,heldout,gold=validate_dataset()
    saved=json.loads((ROOT/'evals/results/results.json').read_text())
    if saved['dataset_checksums']!=manifest['files']: raise ValueError('saved run dataset mismatch')
    registry=Registry(DATA/'artifacts'); full=Witness(saved['scope'],registry,now=NOW)
    initial={ref for q in learning+heldout for ref in q['sources']}
    existing=set()
    with full.readonly():
        for ref in registry.items:
            artifact = full.source(ref)
            if artifact is not None:
                if artifact != registry.get(ref): raise ValueError('full graph artifact differs from frozen registry: '+ref)
                existing.add(ref)
        observed_full=evaluate(full,heldout,gold,'graph')
    expected_full=saved['checkpoints'][-1]['evaluation']['predictions']
    if [(p['id'],p['predicted'],p['roots']) for p in observed_full['predictions']] != [(p['id'],p['predicted'],p['roots']) for p in expected_full]:
        raise RuntimeError('preserved full graph no longer matches recorded results')
    learned=existing-initial
    if len(learned)!=sum(x['sources_discovered'] for x in saved['learning_batches']): raise RuntimeError('learned artifact count mismatch')
    w=MetadataWitness('ablation-'+uuid.uuid4().hex,registry,now=NOW)
    for q in heldout: w.seed_claim(q['id'],q['sources'])
    for ref in sorted(existing): w.node('Source',ref,registry.get(ref))
    # Assert no evidence relationships exist for every available source in isolated scope.
    with w.readonly():
        for ref in sorted(existing):
            for rel in ('DERIVED_FROM','REQUIRES'):
                rows=w.q(f'MATCH (s:Source {{id: $id}})-[:{rel}]->(t:Source) RETURN t.id AS id',{'id':w.nid('Source',ref)})
                if rows: raise RuntimeError('unexpected provenance edge')
    ablation=evaluate(w,heldout,gold,'graph')
    result={'dataset_version':manifest['dataset_version'],'dataset_checksums':manifest['files'],'preserved_full_scope':saved['scope'],'artifact_only_scope':w.scope,'learned_artifacts':sorted(learned),'available_artifacts':sorted(existing),'static':saved['static'],'artifact_only':ablation,'full':observed_full,'method':'Artifact-only reads the same available HydraDB Source nodes and resolves declared references at assessment time; it does not read or write provenance edges. Policy logic is shared.'}
    OUT.mkdir(exist_ok=True);(OUT/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('learned artifacts:',len(learned),sorted(learned))
    for name in ('static','artifact_only','full'):
        x=result[name]; print(name,'accuracy',x['accuracy'],'roots',x['root_accuracy'],'false approvals',x['false_approval'],'gaps',x['unanswered_gaps'],'queries',x['queries']['query_count'],'p95 ms',round(x['queries']['p95_ms'],2))

if __name__=='__main__': main()
