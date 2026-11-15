import json
from pathlib import Path
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from evals.run import validate_dataset
from hydrawitness.engine import Registry, Witness

class BenchmarkIntegrity(unittest.TestCase):
    def test_frozen_split(self):
        manifest,learn,held,gold=validate_dataset()
        self.assertEqual((len(learn),len(held),len(gold)),(40,20,20))
        self.assertFalse({q['id'] for q in learn}&{q['id'] for q in held})
        self.assertTrue({q['group'] for q in held}-{q['group'] for q in learn})
    def test_readonly_guard_and_incomplete_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            common={'type':'report','observed_at':'2026-11-14T00:00:00Z','required':[]}
            data=[{**common,'external_id':'mixed/report','references':['mixed/root','mixed/missing']}, {**common,'external_id':'mixed/root','references':[],'root_verified':True}]
            for i,a in enumerate(data): (Path(directory)/f'{i}.json').write_text(json.dumps(a))
            w=Witness('test-'+uuid.uuid4().hex,Registry(directory),now=datetime(2026,11,14,12,tzinfo=timezone.utc))
            w.seed_claim('claim',['mixed/report'])
            result=w.improve('claim',{'id':'basic'})['after']
            self.assertEqual(result['verdict'],'REVIEW_REQUIRED')
            self.assertEqual(result['verified_roots'],[])
            with w.readonly():
                w.assess('claim',{'id':'basic'})
                with self.assertRaises(RuntimeError): w.q('CREATE (n:Bad {id: 123})')
                with self.assertRaises(RuntimeError): w.q('MATCH (n:Bad {id: 123}) DELETE n')
    def test_scan_failure_policy_is_explicit(self):
        registry=Registry(Path(__file__).resolve().parent.parent/'datasets/controlled')
        w=Witness('test-'+uuid.uuid4().hex,registry,now=datetime(2026,11,14,12,tzinfo=timezone.utc))
        w.seed_claim('claim',['contradiction/report'])
        result=w.improve('claim',{'id':'no-scan-required'})
        self.assertEqual(result['after']['verdict'],'REVIEW_REQUIRED')
        self.assertEqual(w.assess('claim',{'id':'scan-required','require_security_scan':True})['verdict'],'BLOCK')

if __name__=='__main__': unittest.main()
