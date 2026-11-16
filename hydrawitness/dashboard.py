"""Replayable synthetic dashboard backed by the same live Witness engine as MCP."""
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import threading
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from .mcp_server import ROOT, SCOPE, result, trace, witness
from .seed_codex import DEPLOYMENT_CLAIM, SECURITY_CLAIM, seed_checkout

POLICY = 'release-v1'
GRAPH_WRITE_LOCK = threading.Lock()


def scenario_scope(scenario):
    return f'{SCOPE}-scenario-{scenario}'


def state(w):
    data = result(w, DEPLOYMENT_CLAIM, POLICY)
    with (ROOT / 'evals/results/iterations.csv').open(newline='') as file:
        data['accuracy'] = [
            {'iteration': int(row['iteration']), 'correct': int(row['accuracy_correct']),
             'total': int(row['accuracy_total'])}
            for row in csv.DictReader(file)
        ]
    return data


class Handler(BaseHTTPRequestHandler):
    def send(self, body, code=200, kind='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def graph(self, request):
        scenarios = parse_qs(request.query, keep_blank_values=True).get('scenario')
        if scenarios is None:
            return witness()
        if len(scenarios) != 1 or not re.fullmatch('[0-9a-f]{32}', scenarios[0]):
            raise ValueError('Invalid demo scenario')
        return witness(scenario_scope(scenarios[0]))

    def do_GET(self):
        request = urlsplit(self.path)
        try:
            if request.path == '/':
                self.send((ROOT / 'frontend/index.html').read_bytes(), kind='text/html; charset=utf-8')
            elif request.path == '/api/state':
                self.send(state(self.graph(request)))
            elif request.path == '/api/follow-up':
                data = result(self.graph(request), SECURITY_CLAIM, POLICY)
                data.update(sources_ingested=0, edges_added=0)
                self.send(data)
            elif request.path == '/api/scan-impact':
                scan_ids = parse_qs(request.query, keep_blank_values=True).get('scan_id', [])
                if len(scan_ids) != 1 or not scan_ids[0]:
                    raise ValueError('Specify exactly one scan_id')
                self.send(self.graph(request).scan_impact(scan_ids[0]))
            else:
                self.send({'error': 'Not found'}, 404)
        except ValueError as exc:
            self.send({'error': str(exc)}, 400)
        except Exception as exc:
            self.send({'error': str(exc)}, 503)

    def do_POST(self):
        request = urlsplit(self.path)
        if request.path not in ('/api/scenario', '/api/improve'):
            return self.send({'error': 'Not found'}, 404)
        public_host = os.getenv('RENDER_EXTERNAL_HOSTNAME')
        host = public_host or f'127.0.0.1:{self.server.server_port}'
        expected = f"{'https' if public_host else 'http'}://{host}"
        if self.headers.get('Origin') != expected or self.headers.get('Host') != host:
            return self.send({'error': 'Invalid request origin'}, 403)
        try:
            if request.path == '/api/scenario':
                scenario = uuid4().hex
                w = witness(scenario_scope(scenario))
                with GRAPH_WRITE_LOCK:
                    seed_checkout(w)
                self.send({**state(w), 'scenario': scenario}, 201)
                return
            w = self.graph(request)
            with GRAPH_WRITE_LOCK:
                improvement = w.improve(DEPLOYMENT_CLAIM, POLICY, 5)
            with w.readonly():
                graph = trace(w, claim_id=DEPLOYMENT_CLAIM)
            self.send({'improvement': improvement, 'provenance': graph,
                       'hydradb_query_count': w.queries, 'graph_scope': w.scope})
        except ValueError as exc:
            self.send({'error': str(exc)}, 400)
        except Exception as exc:
            self.send({'error': str(exc)}, 503)


if __name__ == '__main__':
    port = int(os.getenv('HYDRAWITNESS_PORT', '8765'))
    print(f'HydraWitness dashboard: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
