"""Frozen synthetic cross-question experiment; all graph operations use HydraDB."""
import argparse
import csv
import random
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time
import uuid
from hydrawitness.engine import Registry, Witness

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'datasets/benchmark'
OUT=ROOT/'evals/results'
NOW=datetime(2026,11,14,12,tzinfo=timezone.utc)

def load_json(path): return json.loads(path.read_text())

def validate_dataset():
    manifest=load_json(DATA/'checksums.json')
    actual={str(p.relative_to(DATA)) for p in [DATA/'learning.json',DATA/'heldout.json',DATA/'gold.json',*(DATA/'artifacts').glob('*.json')]}
    if actual != set(manifest['files']): raise ValueError('benchmark file set mismatch')
    for name,expected in manifest['files'].items():
        if hashlib.sha256((DATA/name).read_bytes()).hexdigest()!=expected: raise ValueError('checksum mismatch: '+name)
    learning=load_json(DATA/'learning.json'); heldout=load_json(DATA/'heldout.json'); gold=load_json(DATA/'gold.json')
    ids=[x['id'] for x in learning+heldout]
    if len(learning)!=40 or len(heldout)!=20 or len(ids)!=len(set(ids)) or set(gold)!={x['id'] for x in heldout}: raise ValueError('split integrity error')
    if any(v['verdict'] not in ('APPROVE','BLOCK','REVIEW_REQUIRED') for v in gold.values()): raise ValueError('bad label')
    return manifest,learning,heldout,gold

def percentile(values, fraction):
    values=sorted(values)
    if not values: return None
    # Nearest rank, including endpoints.
    import math
    return values[max(0,math.ceil(len(values)*fraction)-1)]

def stats(log):
    durations=[q['duration_ms'] for q in log]
    by_shape={}
    for q in log:
        shape=q['cypher']; item=by_shape.setdefault(shape,{'count':0,'total_ms':0.0});item['count']+=1;item['total_ms']+=q['duration_ms']
    return {'query_count':len(log),'p50_ms':percentile(durations,.5),'p95_ms':percentile(durations,.95),'query_shapes':by_shape}

def flat(w, q):
    # Document-level heuristic: count reports as independent; no referenced artifacts traversed.
    docs=w.attached(q['id']); policy=q['policy']; fresh=[]
    for d in docs:
        dt=datetime.fromisoformat(d['observed_at'].replace('Z','+00:00'))
        if dt<=NOW and (NOW-dt).total_seconds()<=policy.get('max_age_days',365)*86400: fresh.append(d)
    scan=[d for d in fresh if d['type']=='security_scan']
    if policy.get('require_security_scan') and any(x.get('outcome') in ('failed','skipped') for x in scan): verdict='BLOCK'
    elif len(fresh)!=len(docs) or len(fresh)<policy.get('min_roots',1) or (policy.get('require_security_scan') and not any(x.get('outcome')=='passed' for x in scan)): verdict='REVIEW_REQUIRED'
    else: verdict='APPROVE'
    return {'verdict':verdict,'verified_roots':sorted(x['external_id'] for x in fresh),'gaps':[]}

def evaluate(w, questions, gold, mode):
    results=[]; start=time.perf_counter(); index=len(w.query_log)
    with w.readonly():
        for q in questions:
            result=flat(w,q) if mode=='flat' else w.assess(q['id'],q['policy'])
            results.append({'id':q['id'],'group':q['group'],'expected':gold[q['id']]['verdict'],'predicted':result['verdict'],'expected_roots':gold[q['id']]['verified_roots'],'roots':result['verified_roots'],'gap_count':len(result['gaps'])})
    count=len(results); correct=sum(x['expected']==x['predicted'] for x in results)
    nonapproves=[x for x in results if x['expected']!='APPROVE']; false=sum(x['predicted']=='APPROVE' for x in nonapproves)
    review=[x for x in results if x['expected']=='REVIEW_REQUIRED']; review_correct=sum(x['predicted']=='REVIEW_REQUIRED' for x in review)
    root_correct=sum(set(x['roots'])==set(x['expected_roots']) for x in results)
    return {'accuracy':{'numerator':correct,'denominator':count,'rate':correct/count},'false_approval':{'numerator':false,'denominator':len(nonapproves),'rate':false/len(nonapproves) if nonapproves else None},'correct_review':{'numerator':review_correct,'denominator':len(review),'rate':review_correct/len(review) if review else None},'root_accuracy':{'numerator':root_correct,'denominator':count,'rate':root_correct/count},'unanswered_gaps':sum(x['gap_count'] for x in results),'duration_seconds':time.perf_counter()-start,'queries':stats(w.query_log[index:]),'predictions':results}

def write_svg(results, path):
    points=results['checkpoints']; top=70; bottom=350; left=95; right=690
    def xy(i,y): return (left+(right-left)*i/4,bottom-(bottom-top)*y)
    coords=[xy(c['iteration'],c['evaluation']['accuracy']['rate']) for c in points]
    flat=results['static']['accuracy']['rate']; sy=xy(0,flat)[1]
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="440" viewBox="0 0 760 440">','<rect width="100%" height="100%" fill="#fff"/>','<g font-family="Arial, sans-serif" fill="#172534">','<text x="45" y="32" font-size="20" font-weight="bold">Held-out decision accuracy vs. learning iteration</text>']
    for n in range(0,101,20):
        y=xy(0,n/100)[1];out += [f'<line x1="{left}" x2="{right}" y1="{y}" y2="{y}" stroke="#e2e8ef"/>',f'<text x="50" y="{y+5}" font-size="13">{n}%</text>']
    out += [f'<line x1="{left}" x2="{right}" y1="{sy}" y2="{sy}" stroke="#929ba8" stroke-width="3" stroke-dasharray="7 5"/>',f'<polyline fill="none" stroke="#166b82" stroke-width="4" points="{" ".join(f"{x},{y}" for x,y in coords)}"/>']
    for c,(x,y) in zip(points,coords):
        out += [f'<circle cx="{x}" cy="{y}" r="5" fill="#166b82"/>', f'<text x="{x-10}" y="{y-12}" font-size="13">{c["evaluation"]["accuracy"]["numerator"]}/20</text>',f'<text x="{x-4}" y="{bottom+22}" font-size="13">{c["iteration"]}</text>']
    out += ['<text x="210" y="420" font-size="13">Learning batch</text>','<text x="360" y="420" fill="#166b82" font-size="13">● HydraWitness</text>','<text x="520" y="420" fill="#707b89" font-size="13">--- Static graph</text>','</g></svg>']
    path.write_text('\n'.join(out))

def run(seed=0, output_dir=OUT):
    manifest,learning,heldout,gold=validate_dataset(); registry=Registry(DATA/'artifacts')
    if seed: random.Random(seed).shuffle(learning)
    scope='benchmark-'+uuid.uuid4().hex; w=Witness(scope,registry,now=NOW)
    start=time.perf_counter()
    for q in learning+heldout: w.seed_claim(q['id'],q['sources'])
    seed_stats=stats(w.query_log); flat_result=evaluate(w,heldout,gold,'flat'); initial=evaluate(w,heldout,gold,'graph')
    result={'ordering_seed':seed,'dataset_version':manifest['dataset_version'],'dataset_checksums':manifest['files'],'scope':scope,'evaluation_time':NOW.isoformat(),'seed_stats':seed_stats,'flat':flat_result,'static':initial,'checkpoints':[{'iteration':0,'learning_processed':0,'sources_discovered':0,'relationships_added':0,'evaluation':initial}],'learning_batches':[]}
    for batch in range(4):
        start_log=len(w.query_log); batch_start=time.perf_counter(); sources=edges=0
        # Gold and held-out labels are not provided to the improvement loop.
        for q in learning[batch*10:(batch+1)*10]:
            r=w.improve(q['id'],q['policy']);sources+=r['sources_ingested'];edges+=r['edges_added']
        learning_log=stats(w.query_log[start_log:]); learning_duration=time.perf_counter()-batch_start
        evaluation=evaluate(w,heldout,gold,'graph')
        result['learning_batches'].append({'iteration':batch+1,'question_ids':[q['id'] for q in learning[batch*10:(batch+1)*10]],'sources_discovered':sources,'relationships_added':edges,'duration_seconds':learning_duration,'queries':learning_log})
        result['checkpoints'].append({'iteration':batch+1,'learning_processed':10*(batch+1),'sources_discovered':sources,'relationships_added':edges,'evaluation':evaluation})
    result['total_duration_seconds']=time.perf_counter()-start; result['all_queries']=stats(w.query_log)
    OUT = Path(output_dir)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    with (OUT/'iterations.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['iteration','learning_processed','accuracy_correct','accuracy_total','accuracy','static_accuracy','false_approvals','non_approval_gold','correct_reviews','review_gold','roots_correct','root_total','gaps','sources_discovered','relationships_added','queries','p50_ms','p95_ms']);writer.writeheader()
        for c in result['checkpoints']:
            e=c['evaluation']; writer.writerow({'iteration':c['iteration'],'learning_processed':c['learning_processed'],'accuracy_correct':e['accuracy']['numerator'],'accuracy_total':e['accuracy']['denominator'],'accuracy':e['accuracy']['rate'],'static_accuracy':initial['accuracy']['rate'],'false_approvals':e['false_approval']['numerator'],'non_approval_gold':e['false_approval']['denominator'],'correct_reviews':e['correct_review']['numerator'],'review_gold':e['correct_review']['denominator'],'roots_correct':e['root_accuracy']['numerator'],'root_total':e['root_accuracy']['denominator'],'gaps':e['unanswered_gaps'],'sources_discovered':c['sources_discovered'],'relationships_added':c['relationships_added'],'queries':e['queries']['query_count'],'p50_ms':e['queries']['p50_ms'],'p95_ms':e['queries']['p95_ms']})
    write_svg(result,OUT/'accuracy.svg')
    lines=['# Synthetic learning experiment','','This report is generated from live HydraDB runs; see docs/evaluation.md for protocol and limitations.','','| Iteration | Accuracy | Root sets correct | False approvals | Correct reviews | Open gaps | Sources added | Relationships added |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in result['checkpoints']:
        e=c['evaluation'];fmt=lambda m:f"{m['numerator']}/{m['denominator']}";lines.append(f"| {c['iteration']} | {fmt(e['accuracy'])} | {fmt(e['root_accuracy'])} | {fmt(e['false_approval'])} | {fmt(e['correct_review'])} | {e['unanswered_gaps']} | {c['sources_discovered']} | {c['relationships_added']} |")
    lines += ['',f"Flat baseline accuracy: {result['flat']['accuracy']['numerator']}/{len(heldout)}. Static baseline accuracy: {initial['accuracy']['numerator']}/{len(heldout)}.",f"Total: {result['all_queries']['query_count']} queries in {result['total_duration_seconds']:.2f}s; query p50 {result['all_queries']['p50_ms']:.2f}ms, p95 {result['all_queries']['p95_ms']:.2f}ms.",'','The curve measures cross-question reuse within shared synthetic artifact groups; it does not establish transfer to unrelated organizations or documents.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',type=int,default=0,help='deterministic learning-order shuffle; 0 uses frozen order')
    parser.add_argument('--output-dir',type=Path,default=OUT)
    args=parser.parse_args()
    run(args.seed,args.output_dir)
