"""Live HydraDB integration; unique scope per test, never resets existing data."""
from tests import integration_test
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from hydrawitness.engine import Registry, Witness, validate
from hydrawitness.proof import query
from hydrawitness.seed_codex import CHECKOUT_SUBJECT

ROOT=Path(__file__).resolve().parent.parent
NOW=datetime(2026,11,14,12,tzinfo=timezone.utc)

class LiveHydraTest(unittest.TestCase):
    def setUp(self):
        self.w=Witness('test-'+uuid.uuid4().hex,Registry(ROOT/'datasets/controlled'),now=NOW)
    @integration_test
    def test_scenarios(self):
        for scenario in json.loads((ROOT/'datasets/scenarios.json').read_text()):
            with self.subTest(scenario=scenario['id']):
                self.w.seed_claim(scenario['id'],scenario['sources'],subject=scenario.get('subject'))
                result=self.w.improve(scenario['id'],scenario['policy'])
                self.assertEqual(result['after']['verdict'],scenario['expected'],result)
                if scenario['id']=='cycle':
                    self.assertIn('cycle',{g['kind'] for g in result['after']['gaps']})
                    self.assertEqual(result['after']['verified_roots'],[])
                if scenario['id']=='unverified-root':
                    self.assertEqual(result['after']['verified_roots'],[])
                if scenario['id']=='missing-reference':
                    self.assertIn('missing_reference',{g['kind'] for g in result['after']['gaps']})
                if scenario['id']=='independent': self.assertEqual(len(result['after']['verified_roots']),2)
    @integration_test
    def test_repair_is_reused_and_history_persisted(self):
        policy={'id':'release','require_security_scan':True}
        self.w.seed_claim('one',['demo/qa','demo/security-summary'],subject=CHECKOUT_SUBJECT)
        self.w.seed_claim('two',['demo/qa'],subject=CHECKOUT_SUBJECT)
        one=self.w.improve('one',policy)
        self.assertEqual((one['before']['verdict'],one['after']['verdict']),('REVIEW_REQUIRED','BLOCK'))
        self.assertEqual(one['sources_ingested'],2)
        self.assertEqual(one['edges_added'],3)
        fresh=Witness(self.w.scope,self.w.registry,now=NOW)
        two=fresh.improve('two',policy)
        self.assertEqual(two['before']['verdict'],'BLOCK')
        self.assertEqual((two['sources_ingested'],two['edges_added']),(0,0))
        rows=fresh.q('MATCH (i:Improvement)-[:FOR_CLAIM]->(c:Claim {id: $id}) RETURN i.payload AS payload',{'id':fresh.nid('Claim','one')})
        self.assertEqual(len(rows),len(one['history']))
        self.assertTrue(any(json.loads(r['payload'])['decision_changed'] for r in rows))
        self.assertEqual(fresh.improve('one',policy)['edges_added'],0)
        bounded=fresh.q('MATCH (s:Source {id: $id})-[:DERIVED_FROM*1..5]->(p:Source) RETURN DISTINCT p.payload AS payload',{'id':fresh.nid('Source','demo/security-summary')})
        self.assertEqual({json.loads(x['payload'])['external_id'] for x in bounded},{'demo/qa','demo/ci'})
    @integration_test
    def test_depth_limit_is_uncertainty(self):
        self.w.max_depth=1
        self.w.seed_claim('depth',['multihop/a'])
        result=self.w.improve('depth',{'id':'basic'})
        self.assertEqual(result['after']['verdict'],'REVIEW_REQUIRED')
        self.assertIn('depth_limit',{g['kind'] for g in result['after']['gaps']})
    @integration_test
    def test_query_errors_propagate(self):
        with self.assertRaises(RuntimeError): query('THIS IS NOT CYPHER')
    def test_registry_rejects_duplicate_and_unsafe_ids(self):
        a={'external_id':'x','type':'report','observed_at':'2026-11-14T00:00:00Z'}
        with tempfile.TemporaryDirectory() as d:
            for name in ('one.json','two.json'): (Path(d)/name).write_text(json.dumps(a))
            with self.assertRaises(ValueError): Registry(d)
        a['external_id']='../secret'
        with self.assertRaises(ValueError): validate(a)

if __name__=='__main__': unittest.main()
