"""Read-only repeated investigations on equal existing artifacts, alternate order."""
import json,time,statistics
from pathlib import Path
from hydrawitness.engine import Registry,Witness
from evals.ablation import MetadataWitness
from evals.run import DATA,NOW,validate_dataset,percentile
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'evals/repeated-results'
class CountMetadata(MetadataWitness):
 def __init__(self,*a,**k): super().__init__(*a,**k);self.reconstructed=0
 def neighbors(self,ref,relationship):
  found=super().neighbors(ref,relationship);self.reconstructed+=len(found);return found

def main():
 manifest,_,questions,gold=validate_dataset(); old=json.loads((ROOT/'evals/ablation-results/results.json').read_text())
 if old['dataset_checksums']!=manifest['files']:raise ValueError('dataset mismatch')
 registry=Registry(DATA/'artifacts');records=[]
 for rep in range(6):
  for mode in (('graph','metadata') if rep%2==0 else ('metadata','graph')):
   w=(Witness(old['preserved_full_scope'],registry,now=NOW) if mode=='graph' else CountMetadata(old['artifact_only_scope'],registry,now=NOW))
   for q in questions:
    before=w.queries;start=time.perf_counter();start_recon=getattr(w,'reconstructed',0)
    with w.readonly():result=w.assess(q['id'],q['policy'])
    log=w.query_log[-(w.queries-before):];lookups=sum('MATCH (s:Source {id: $id}) RETURN s.payload' in x['cypher'] for x in log)
    records.append({'repetition':rep,'mode':mode,'id':q['id'],'verdict':result['verdict'],'correct':result['verdict']==gold[q['id']]['verdict'],'roots_correct':set(result['verified_roots'])==set(gold[q['id']]['verified_roots']),'queries':w.queries-before,'source_lookups':lookups,'reconstructed_relationships':getattr(w,'reconstructed',0)-start_recon,'duration_ms':(time.perf_counter()-start)*1000,'ingestion_attempts':0})
 summary={}
 for mode in ('graph','metadata'):
  rows=[x for x in records if x['mode']==mode];times=[x['duration_ms'] for x in rows]
  summary[mode]={'investigations':len(rows),'correct':sum(x['correct'] for x in rows),'roots_correct':sum(x['roots_correct'] for x in rows),'queries':sum(x['queries'] for x in rows),'source_lookups':sum(x['source_lookups'] for x in rows),'reconstructed_relationships':sum(x['reconstructed_relationships'] for x in rows),'ingestion_attempts':0,'p50_ms':percentile(times,.5),'p95_ms':percentile(times,.95),'mean_ms':statistics.mean(times)}
 by={(x['repetition'],x['id'],x['mode']):x for x in records}
 for rep in range(6):
  for q in questions:
   if by[rep,q['id'],'graph']['verdict']!=by[rep,q['id'],'metadata']['verdict']:raise RuntimeError('different decisions')
 out={'description':'Six fresh evaluator instances per mode; 20 fixed synthetic held-out claims; alternating mode order. Read-only; no ingestion attempted. Latencies include local HTTP and application evaluation.','summary':summary,'records':records,'artifact_only_scope':old['artifact_only_scope'],'graph_scope':old['preserved_full_scope']}
 OUT.mkdir(exist_ok=True);(OUT/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
