"""Exercise independent browser scenarios and cross-claim reuse against HydraDB."""
from tests import integration_test
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hydrawitness.dashboard import Handler, witness


class ScanImpactRouteTest(unittest.TestCase):
    def request(self, path):
        handler = object.__new__(Handler)
        handler.path = path
        handler.send = Mock()
        with patch('hydrawitness.dashboard.witness') as witness:
            handler.do_GET()
        return handler.send.call_args.args, witness

    def test_scan_impact_uses_requested_scenario_and_decodes_scan_id(self):
        scenario = 'a' * 32
        response, witness = self.request(f'/api/scan-impact?scenario={scenario}&scan_id=demo%2Fscan')
        self.assertTrue(witness.call_args.args[0].endswith(f'-scenario-{scenario}'))
        witness.return_value.scan_impact.assert_called_once_with('demo/scan')
        self.assertEqual(response, (witness.return_value.scan_impact.return_value,))

    def test_scan_impact_rejects_missing_or_duplicate_ids(self):
        for query in ('', '?scan_id=', '?scan_id=one&scan_id=two'):
            with self.subTest(query=query):
                response, witness = self.request('/api/scan-impact' + query)
                self.assertEqual(response, ({'error': 'Specify exactly one scan_id'}, 400))
                witness.assert_not_called()


@integration_test
class DashboardTest(unittest.TestCase):
    def test_fresh_scenarios_and_read_only_follow_up(self):
        def fixture_witness(*args):
            graph = witness(*args)
            graph.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
            return graph

        with (patch.dict('os.environ', {'RENDER_EXTERNAL_HOSTNAME': ''}),
              patch('hydrawitness.dashboard.witness', side_effect=fixture_witness)):
            with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    self.exercise_scenarios(f'http://127.0.0.1:{server.server_port}')
                finally:
                    server.shutdown()
                    thread.join()

    def exercise_scenarios(self, origin):
        def request(path, *, method='GET'):
            request = Request(origin + path, method=method, headers={'Origin': origin})
            with urlopen(request, timeout=30) as response:
                return json.load(response)

        first = request('/api/scenario', method='POST')
        second = request('/api/scenario', method='POST')
        first_query = f"?scenario={first['scenario']}"
        second_query = f"?scenario={second['scenario']}"
        self.assertNotEqual(first['graph_scope'], second['graph_scope'])
        self.assertEqual(first['assessment']['verdict'], 'REVIEW_REQUIRED')
        initial_follow_up = request('/api/follow-up' + first_query)
        self.assertEqual(initial_follow_up['assessment']['verdict'], 'REVIEW_REQUIRED')

        repaired = request('/api/improve' + first_query, method='POST')
        self.assertEqual(repaired['graph_scope'], first['graph_scope'])
        improvement = repaired['improvement']
        self.assertEqual(improvement['after']['verdict'], 'BLOCK')
        self.assertGreater(improvement['sources_ingested'], 0)
        self.assertGreater(improvement['edges_added'], 0)

        follow_up = request('/api/follow-up' + first_query)
        assessment = follow_up['assessment']
        self.assertEqual(follow_up['graph_scope'], first['graph_scope'])
        self.assertNotEqual(assessment['claim_id'], improvement['after']['claim_id'])
        self.assertEqual(assessment['verdict'], 'BLOCK')
        self.assertEqual(assessment['verified_roots'], ['demo/ci'])
        self.assertIn({'kind': 'contradictory_outcome', 'reference': 'demo/scan',
                       'outcome': 'skipped'}, assessment['gaps'])
        self.assertEqual((follow_up['sources_ingested'], follow_up['edges_added']), (0, 0))
        self.assertGreater(follow_up['hydradb_query_count'], 0)

        impact = request('/api/scan-impact' + first_query + '&scan_id=demo%2Fscan')
        self.assertEqual([item['claim_id'] for item in impact['impacted_claims']],
                         ['checkout-deployment', 'checkout-security'])
        for item in impact['impacted_claims']:
            self.assertEqual(item['status'], 'REASSESSMENT_REQUIRED')
            self.assertEqual(item['path'][-1], {'from': 'demo/ci', 'to': 'demo/scan', 'type': 'REQUIRES'})
        with self.assertRaises(HTTPError) as error:
            request('/api/scan-impact' + second_query + '&scan_id=demo%2Fscan')
        error.exception.close()
        self.assertEqual(error.exception.code, 400)

        untouched = request('/api/state' + second_query)
        self.assertEqual(untouched['assessment']['verdict'], 'REVIEW_REQUIRED')
        self.assertNotIn('demo/scan', {source['id'] for source in untouched['provenance']['sources']})
