"""Small live ordering tests without touching any existing graph scope."""
from tests import integration_test
from datetime import datetime,timezone
from pathlib import Path
import unittest
import uuid
import urllib.error
from unittest.mock import patch
from hydrawitness.proof import query
from hydrawitness.engine import Registry,Witness
from hydrawitness.seed_codex import CHECKOUT_SUBJECT
from evals.ablation import MetadataWitness

ROOT=Path(__file__).resolve().parent.parent
NOW=datetime(2026,11,14,12,tzinfo=timezone.utc)

class ReverseWitness(Witness):
    def resolve(self,gaps): return super().resolve(list(reversed(gaps)))

class Robustness(unittest.TestCase):
    @integration_test
    def test_question_and_evidence_order(self):
        registry=Registry(ROOT/'datasets/controlled'); policy={'id':'release','require_security_scan':True}
        results=[]
        for cls,reverse in ((Witness,False),(ReverseWitness,True)):
            w=cls('order-'+uuid.uuid4().hex,registry,now=NOW)
            questions=[('a',['demo/qa','demo/security-summary']),('b',['demo/security-summary','demo/qa'])]
            if reverse: questions.reverse()
            for name,refs in questions: w.seed_claim(name,refs,subject=CHECKOUT_SUBJECT)
            before={name:w.assess(name,policy)['verdict'] for name,_ in questions}
            for name,_ in questions: w.improve(name,policy)
            after={name:w.assess(name,policy) for name,_ in questions}
            self.assertEqual(set(before.values()),{'REVIEW_REQUIRED'})
            self.assertEqual({x['verdict'] for x in after.values()},{'BLOCK'})
            self.assertTrue(all(x['verified_roots']==['demo/ci'] for x in after.values()))
            self.assertEqual(w.improve('a',policy)['sources_ingested'],0)
            results.append({k:(v['verdict'],v['verified_roots']) for k,v in after.items()})
        self.assertEqual(results[0],results[1])
    def test_unavailable_database_is_an_error(self):
        with patch('hydrawitness.proof.urllib.request.urlopen', side_effect=urllib.error.URLError('offline')):
            with self.assertRaises(urllib.error.URLError):
                query('MATCH (n:Source {id: 1}) RETURN n.id AS id')
    @integration_test
    def test_metadata_reads_only_existing_documents(self):
        registry=Registry(ROOT/'datasets/controlled');w=MetadataWitness('metadata-'+uuid.uuid4().hex,registry,now=NOW)
        w.seed_claim('one',['demo/qa'],subject=CHECKOUT_SUBJECT)
        self.assertEqual(w.assess('one',{'id':'release','require_security_scan':True})['verdict'],'REVIEW_REQUIRED')
        w.node('Source','demo/ci',registry.get('demo/ci'))
        w.node('Source','demo/scan',registry.get('demo/scan'))
        result=w.assess('one',{'id':'release','require_security_scan':True})
        self.assertEqual(result['verdict'],'BLOCK')
        self.assertEqual(result['verified_roots'],['demo/ci'])
        self.assertFalse(w.q('MATCH (s:Source {id: $id})-[:DERIVED_FROM]->(t:Source) RETURN t.id AS id',{'id':w.nid('Source','demo/qa')}))

if __name__=='__main__':unittest.main()
