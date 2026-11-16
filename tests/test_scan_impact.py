"""Offline tests for directed, subject-bound reverse impact traversal."""
import json
import unittest
from datetime import datetime, timezone

from hydrawitness.engine import Witness


SUBJECT = {'kind': 'git_commit', 'value': 'a' * 40}
OTHER = {'kind': 'git_commit', 'value': 'b' * 40}


def source(ref, *, kind='report', references=(), required=(), subject=None):
    item = {'external_id': ref, 'type': kind, 'references': list(references),
            'required': list(required), 'observed_at': '2020-01-01T00:00:00Z'}
    if subject is not None:
        item['subject'] = subject
    return item


class OfflineWitness(Witness):
    def __init__(self, sources, edges, claims, supports, *, max_depth=8):
        super().__init__('offline', None, max_depth=max_depth,
                         now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.sources = {s['external_id']: s for s in sources}
        self.edges = edges
        self.claims = {c['claim_id']: c for c in claims}
        self.supports = supports

    def source(self, ref):
        assert self.read_only
        return self.sources.get(ref)

    def reverse_sources(self, ref, relationship):
        assert self.read_only
        return [self.sources[src] for src, rel, dst in self.edges
                if rel == relationship and dst == ref]

    def supporting_claims(self, ref):
        assert self.read_only
        return [self.claims[claim] for src, claim in self.supports if src == ref]

    def q(self, cypher, params=None):
        raise AssertionError('offline traversal must use the supplied graph reads')


def claim(ref, subject=SUBJECT):
    return {'claim_id': ref, 'subject': subject}


class ScanImpactTests(unittest.TestCase):
    def test_shared_scan_returns_matching_claims_with_directed_paths(self):
        scan = source('scan', kind='security_scan', subject=SUBJECT)
        scan['outcome'] = 'failed'  # Impact is independent of outcome and age.
        ci = source('ci', kind='ci', required=['scan'])
        first = source('report-a', references=['ci'])
        second = source('report-b', references=['ci'])
        witness = OfflineWitness([scan, ci, first, second],
            [('ci', 'REQUIRES', 'scan'), ('report-a', 'DERIVED_FROM', 'ci'),
             ('report-b', 'DERIVED_FROM', 'ci')],
            [claim('a'), claim('b'), claim('wrong', OTHER), claim('unbound', None)],
            [('report-a', 'a'), ('report-b', 'b'), ('report-a', 'wrong'),
             ('report-b', 'unbound')])
        result = witness.scan_impact('scan')
        self.assertEqual(result['scan_id'], 'scan')
        self.assertEqual(result['subject'], SUBJECT)
        impacts = {item['claim_id']: item for item in result['impacted_claims']}
        self.assertEqual(set(impacts), {'a', 'b'})
        for name, report in (('a', 'report-a'), ('b', 'report-b')):
            self.assertEqual(impacts[name]['status'], 'REASSESSMENT_REQUIRED')
            self.assertEqual(impacts[name]['path'], [
                {'from': report, 'to': name, 'type': 'SUPPORTS'},
                {'from': report, 'to': 'ci', 'type': 'DERIVED_FROM'},
                {'from': 'ci', 'to': 'scan', 'type': 'REQUIRES'},
            ])
        self.assertFalse(witness.read_only)

    def test_undeclared_edges_do_not_establish_impact(self):
        scan = source('scan', kind='security_scan', subject=SUBJECT)
        bad_ci = source('bad-ci', kind='ci')
        ci = source('ci', kind='ci', required=['scan'])
        bad_report = source('bad-report')
        witness = OfflineWitness([scan, bad_ci, ci, bad_report],
            [('bad-ci', 'REQUIRES', 'scan'), ('ci', 'REQUIRES', 'scan'),
             ('bad-report', 'DERIVED_FROM', 'ci')],
            [claim('bad-required'), claim('bad-derived')],
            [('bad-ci', 'bad-required'), ('bad-report', 'bad-derived')])
        self.assertEqual(witness.scan_impact('scan')['impacted_claims'], [])

    def test_cycles_and_duplicate_routes_choose_one_shortest_path(self):
        scan = source('scan', kind='security_scan', subject=SUBJECT)
        ci = source('ci', kind='ci', required=['scan'], references=['long'])
        short = source('short', references=['ci'])
        long = source('long', references=['short'])
        witness = OfflineWitness([scan, ci, short, long],
            [('ci', 'REQUIRES', 'scan'), ('short', 'DERIVED_FROM', 'ci'),
             ('long', 'DERIVED_FROM', 'short'), ('ci', 'DERIVED_FROM', 'long')],
            [claim('same')], [('short', 'same'), ('long', 'same')])
        items = witness.scan_impact('scan')['impacted_claims']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['path'], [
            {'from': 'short', 'to': 'same', 'type': 'SUPPORTS'},
            {'from': 'short', 'to': 'ci', 'type': 'DERIVED_FROM'},
            {'from': 'ci', 'to': 'scan', 'type': 'REQUIRES'},
        ])

    def test_depth_limit_excludes_paths_forward_assessment_cannot_reach(self):
        scan = source('scan', kind='security_scan', subject=SUBJECT)
        ci = source('ci', kind='ci', required=['scan'])
        report = source('report', references=['ci'])
        witness = OfflineWitness([scan, ci, report],
            [('ci', 'REQUIRES', 'scan'), ('report', 'DERIVED_FROM', 'ci')],
            [claim('direct'), claim('deep')], [('ci', 'direct'), ('report', 'deep')], max_depth=1)
        self.assertEqual([x['claim_id'] for x in witness.scan_impact('scan')['impacted_claims']],
                         ['direct'])

    def test_reverse_helpers_discard_rows_from_other_scopes(self):
        witness = Witness('ours', None)
        other = Witness('other', None)
        payload = source('ci', kind='ci', required=['scan'])
        calls = []
        def query(cypher, params):
            calls.append((cypher, params))
            return [{'id': witness.nid('Source', 'ci'), 'payload': json.dumps(payload)},
                    {'id': other.nid('Source', 'ci'), 'payload': json.dumps(payload)}]
        witness.q = query
        self.assertEqual(witness.reverse_sources('scan', 'REQUIRES'), [payload])
        self.assertEqual(calls[0][1]['id'], witness.nid('Source', 'scan'))
        with self.assertRaises(ValueError):
            witness.reverse_sources('scan', 'SUPPORTS')

    def test_invalid_scan_identifier_is_rejected_before_graph_lookup(self):
        witness = Witness('ours', None)
        def unexpected_query(*args):
            self.fail('invalid scan ID reached the graph')
        witness.q = unexpected_query
        for ref in ('', '../scan', 'scan?query', 'x' * 201, None):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, 'invalid scan identifier'):
                witness.scan_impact(ref)

    def test_unknown_non_scan_and_unbound_scan(self):
        witness = OfflineWitness([source('report'), source('unbound', kind='security_scan')],
                                 [], [], [])
        for ref in ('missing', 'report'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                witness.scan_impact(ref)
        self.assertEqual(witness.scan_impact('unbound')['impacted_claims'], [])
        self.assertFalse(witness.read_only)


if __name__ == '__main__':
    unittest.main()
