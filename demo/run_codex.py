"""Run two real Codex CLI sessions against a fresh shared synthetic graph scope."""
import json,os,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
scope='codex-'+uuid.uuid4().hex[:12]
env={**os.environ,'HYDRAWITNESS_SCOPE':scope}
subprocess.run([sys.executable,'-m','hydrawitness.seed_codex'],cwd=ROOT,env=env,check=True)
prompts=[
 'You are an advisory release agent. Can we safely deploy checkout-v2? Call the hydrawitness verify_evidence MCP tool for claim_id checkout-deployment and policy_id release-v1. Then call assess_and_improve for the same claim and explain the actual results. The evidence is synthetic; do not deploy.',
 'You are an advisory security agent in a fresh session. Is checkout-v2 ready for production? Call the hydrawitness verify_evidence MCP tool for claim_id checkout-security and policy_id release-v1. Explain the returned graph evidence. Do not ingest or deploy.'
]
out=ROOT/'demo'/'runs'/scope;out.mkdir(parents=True,exist_ok=False)
for number,prompt in enumerate(prompts,1):
 result=subprocess.run(['codex','exec','--json','--skip-git-repo-check','-C',str(ROOT),prompt],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True)
 events=[json.loads(line) for line in result.stdout.splitlines()]
 # Keep original HydraWitness calls and agent events; omit unrelated MCP context and stderr.
 filtered=[e for e in events if e.get('item',{}).get('type')!='mcp_tool_call' or e['item'].get('server')=='hydrawitness']
 calls=[e['item']['tool'] for e in filtered if e.get('type')=='item.completed' and e.get('item',{}).get('server')=='hydrawitness']
 required=['verify_evidence','assess_and_improve'] if number==1 else ['verify_evidence']
 if not all(name in calls for name in required) or (number==2 and 'assess_and_improve' in calls):raise RuntimeError(f'Unexpected Codex tool calls: {calls}')
 (out/f'session-{number}.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in filtered))
 print(f'Session {number}: {calls}',flush=True)
print('Actual Codex traces:',out,flush=True)
