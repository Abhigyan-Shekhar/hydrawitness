"""Capture real dashboard interaction and a clearly labelled replay of recorded Codex CLI output."""
import html,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'demo'/'recording';OUT.mkdir(exist_ok=True)
def transcript(n):
    events=[json.loads(line) for line in (ROOT/'demo'/f'codex-session-{n}.jsonl').read_text().splitlines()]
    lines=[]
    for event in events:
        item=event.get('item',{})
        if event.get('type')!='item.completed': continue
        if item.get('type')=='mcp_tool_call' and item.get('server')=='hydrawitness':
            obj=item['result'].get('structured_content') or json.loads(item['result']['content'][0]['text'])
            assess=obj.get('assessment',obj.get('improvement',{}).get('after',{}))
            lines.append('MCP  '+item['tool']+'('+json.dumps(item['arguments'])+')')
            lines.append('     verdict: '+str(assess.get('verdict'))+'  •  HydraDB queries: '+str(obj.get('hydradb_query_count')))
            if item['tool']=='assess_and_improve':
                imp=obj['improvement'];lines.append('     sources discovered: '+str(imp['sources_ingested'])+'  •  relationships added: '+str(imp['edges_added']))
        elif item.get('type')=='agent_message':
            lines.append('CODEX  '+item.get('text',''))
    return '\n\n'.join(lines)
pages=[]
for n in (1,2):
    content=html.escape(transcript(n))
    pages.append(f'''<!doctype html><html><head><meta charset="utf-8"><style>body{{background:#10231e;color:#eaf1e8;font:19px/1.55 Menlo,monospace;margin:0;padding:54px 80px}}h1{{font:36px Georgia;margin:18px 0}}.label{{font:700 13px sans-serif;color:#8bc6a8;letter-spacing:.14em}}pre{{white-space:pre-wrap;font:17px/1.65 Menlo,monospace;color:#e3ebe4;background:#1b352c;border:1px solid #3d5d4c;border-radius:12px;padding:28px}}small{{color:#a9bcb0;font:15px sans-serif}}</style></head><body><div class="label">SAVED REAL CODEX CLI OUTPUT · REPLAY · SYNTHETIC EVIDENCE</div><h1>Session {n}: {'Investigate and repair' if n==1 else 'A fresh agent reuses the graph'}</h1><small>Original CLI events, filtered to remove unrelated memory tool calls. No deployment was performed.</small><pre>{content}</pre></body></html>''')
for i,page in enumerate(pages,1):(OUT/f'session-{i}.html').write_text(page)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(OUT),record_video_size={'width':1440,'height':900})
    page=context.new_page();page.goto((OUT/'session-1.html').as_uri());page.wait_for_timeout(12000)
    page.goto(os.environ.get('HYDRAWITNESS_DEMO_URL','http://127.0.0.1:8765/'));page.wait_for_selector('#verdictText');
    if page.locator('#verdictText').inner_text()!='REVIEW REQUIRED': raise RuntimeError('Dashboard scope is not fresh; launch a new scope first')
    page.wait_for_timeout(7000);page.locator('#improve').click();page.wait_for_function("document.querySelector('#verdictText').textContent === 'BLOCK'");page.wait_for_timeout(10000)
    page.goto((OUT/'session-2.html').as_uri());page.wait_for_timeout(12000)
    video=page.video;context.close();path=video.path();browser.close();print(path)
