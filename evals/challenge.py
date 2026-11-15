"""Manually authored topology challenge; labels never enter Witness."""
import hashlib
import json
from pathlib import Path
import uuid
from hydrawitness.engine import Registry, Witness
from evals.run import NOW, evaluate, stats

ROOT=Path(__file__).resolve().parent.parent; DATA=ROOT/'datasets/challenge'; OUT=ROOT/'evals/challenge-results'
def main():
    manifest=json.loads((DATA/'checksums.json').read_text())
    for name,digest in manifest['files'].items():
        if hashlib.sha256((DATA/name).read_bytes()).hexdigest()!=digest: raise ValueError('checksum mismatch '+name)
    questions=json.loads((DATA/'questions.json').read_text()); gold=json.loads((DATA/'gold.json').read_text())
    if len(questions)!=10 or set(gold)!={q['id'] for q in questions}: raise ValueError('invalid challenge split')
    w=Witness('challenge-'+uuid.uuid4().hex,Registry(DATA/'artifacts'),now=NOW)
    for q in questions:w.seed_claim(q['id'],q['sources'])
    initial=evaluate(w,questions,gold,'graph'); start=len(w.query_log); learned=[]
    for q in questions:
        r=w.improve(q['id'],q['policy'])
        learned.append({'id':q['id'],'before':r['before']['verdict'],'after':r['after']['verdict'],'sources':r['sources_ingested'],'edges':r['edges_added']})
    learning_stats=stats(w.query_log[start:]); final=evaluate(w,questions,gold,'graph')
    result={'dataset_version':manifest['dataset_version'],'dataset_checksums':manifest['files'],'scope':w.scope,'initial':initial,'final':final,'learning':learned,'learning_queries':learning_stats}
    OUT.mkdir(exist_ok=True); (OUT/'results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('initial',initial['accuracy'],'final',final['accuracy'],'roots',final['root_accuracy'],'false approvals',final['false_approval'])
    for a,b in zip(initial['predictions'],final['predictions']): print(a['id'],a['predicted'],'->',b['predicted'],'expected',b['expected'],'roots',b['roots'],'expected roots',b['expected_roots'])
    print('learning totals',sum(x['sources'] for x in learned),'sources',sum(x['edges'] for x in learned),'edges',learning_stats['query_count'],'queries')

if __name__=='__main__': main()
