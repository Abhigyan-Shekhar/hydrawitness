"""Local-only dashboard, backed by the same live Witness engine as MCP."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json,os,csv,threading
from .mcp_server import witness,result,trace,SCOPE
ROOT=Path(__file__).resolve().parent.parent
CLAIM='checkout-deployment'
IMPROVE_LOCK=threading.Lock()
class Handler(BaseHTTPRequestHandler):
 def send(self,body,code=200,kind='application/json'):
  if not isinstance(body,bytes): body=json.dumps(body).encode()
  self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  try:
   if self.path=='/':self.send((ROOT/'frontend/index.html').read_bytes(),kind='text/html; charset=utf-8')
   elif self.path=='/api/state':
    w=witness(); data=result(w,CLAIM,'release-v1'); data['accuracy']=[{'iteration':int(row['iteration']),'correct':int(row['accuracy_correct']),'total':int(row['accuracy_total'])} for row in csv.DictReader((ROOT/'evals/results/iterations.csv').read_text().splitlines())]
    self.send(data)
   else:self.send({'error':'Not found'},404)
  except Exception as e:self.send({'error':str(e)},503)
 def do_POST(self):
  if self.path!='/api/improve':return self.send({'error':'Not found'},404)
  public_host=os.getenv('RENDER_EXTERNAL_HOSTNAME')
  host=public_host or f"127.0.0.1:{self.server.server_port}"
  expected=f"{'https' if public_host else 'http'}://{host}"
  if self.headers.get('Origin')!=expected or self.headers.get('Host')!=host:return self.send({'error':'Invalid request origin'},403)
  try:
   with IMPROVE_LOCK:
    w=witness();improvement=w.improve(CLAIM,'release-v1',5)
    with w.readonly():graph=trace(w,claim_id=CLAIM)
   self.send({'improvement':improvement,'provenance':graph,'hydradb_query_count':w.queries,'graph_scope':SCOPE})
  except Exception as e:self.send({'error':str(e)},503)
if __name__=='__main__':
 port=int(os.getenv('HYDRAWITNESS_PORT','8765'));print(f'HydraWitness dashboard: http://127.0.0.1:{port}',flush=True);ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
