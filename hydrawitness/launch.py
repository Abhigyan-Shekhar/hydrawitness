"""Start a fresh local synthetic dashboard without clearing prior graph data."""
import os,uuid
from .seed_codex import main as seed

def main():
 scope='dashboard-'+uuid.uuid4().hex[:12]
 os.environ['HYDRAWITNESS_SCOPE']=scope
 seed()
 print('Fresh scope:',scope,flush=True)
 print('For Codex in this scope: export HYDRAWITNESS_SCOPE='+scope,flush=True)
 from .dashboard import Handler,ThreadingHTTPServer
 port=int(os.getenv('PORT',os.getenv('HYDRAWITNESS_PORT','8765')))
 print(f'Open http://127.0.0.1:{port} (Ctrl-C to stop)',flush=True)
 ThreadingHTTPServer((os.getenv('HYDRAWITNESS_BIND','0.0.0.0' if os.getenv('RENDER_EXTERNAL_HOSTNAME') else '127.0.0.1'),port),Handler).serve_forever()
if __name__=='__main__':main()
