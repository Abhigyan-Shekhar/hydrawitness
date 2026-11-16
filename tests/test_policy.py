"""Offline regression coverage for linked mandatory scan decisions."""
import unittest
from datetime import datetime, timezone

from hydrawitness.engine import Witness, validate


NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)
POLICY = {'id': 'test-release', 'min_roots': 1, 'max_age_days': 30,
          'require_security_scan': True}
MISSING = object()
COMMIT = {'kind': 'git_commit', 'value': 'a' * 40}
DIGEST = {'kind': 'artifact_digest', 'value': 'sha256:' + 'b' * 64}


def scan(ref, outcome='passed', **overrides):
    result = {'external_id': ref, 'type': 'security_scan',
              'observed_at': '2026-01-14T00:00:00Z', 'root_verified': True,
              'subject': COMMIT.copy()}
    if outcome is not MISSING:
        result['outcome'] = outcome
    result.update(overrides)
    if result.get('subject') is MISSING:
        del result['subject']
    return result


def assess(scans, *, linked=None, subject=COMMIT):
    """Use real assessment logic with deterministic in-memory graph reads."""
    root = {'external_id': 'ci', 'type': 'ci', 'observed_at': '2026-01-14T00:00:00Z',
            'root_verified': True, 'required': [s['external_id'] for s in scans]}
    witness = Witness('offline', None, now=NOW)
    witness.claim_subject = lambda claim: subject
    witness.attached = lambda claim: [root]
    witness.neighbors = lambda ref, relationship: (
        [s for s in scans if linked is None or s['external_id'] in linked]
        if ref == 'ci' and relationship == 'REQUIRES' else []
    )
    return witness.assess('claim', POLICY)


class MandatoryScanPolicyTests(unittest.TestCase):
    def test_matching_full_commit_and_digest_approve(self):
        for subject in (COMMIT, {'kind': 'git_commit', 'value': 'c' * 64}, DIGEST):
            with self.subTest(subject=subject):
                result = assess([scan('match', subject=subject)], subject=subject)
                self.assertEqual(result['verdict'], 'APPROVE')
                self.assertEqual(result['subject'], subject)

    def test_different_artifact_digest_requires_review(self):
        other = {'kind': 'artifact_digest', 'value': DIGEST['value'][:-1] + 'c'}
        result = assess([scan('other', subject=other)], subject=DIGEST)
        self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
        self.assertEqual(result['subject'], DIGEST)
        self.assertIn({'kind': 'scan_subject_mismatch', 'reference': 'other',
                       'scan_subject': other}, result['gaps'])

    def test_missing_release_subject_requires_review(self):
        for outcome in ('passed', 'failed', 'skipped'):
            with self.subTest(outcome=outcome):
                result = assess([scan('scan', outcome)], subject=None)
                self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                self.assertTrue(any(g['kind'] == 'missing_release_subject' for g in result['gaps']))
                self.assertFalse(any(g['kind'] == 'contradictory_outcome' for g in result['gaps']))

    def test_missing_or_mismatched_scan_subject_requires_review(self):
        other_commit = {'kind': 'git_commit', 'value': 'd' * 40}
        for subject, gap in ((None, 'missing_scan_subject'), (MISSING, 'missing_scan_subject'),
                             (other_commit, 'scan_subject_mismatch'),
                             (DIGEST, 'scan_subject_mismatch')):
            for outcome in ('passed', 'failed', 'skipped'):
                with self.subTest(subject=subject, outcome=outcome):
                    result = assess([scan('other', outcome, subject=subject)])
                    self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                    self.assertTrue(any(g['kind'] == gap and g['reference'] == 'other'
                                        for g in result['gaps']))
                    self.assertFalse(any(g['kind'] == 'contradictory_outcome' for g in result['gaps']))

    def test_mixed_matching_and_mismatched_scans_require_review(self):
        other = {'kind': 'git_commit', 'value': 'd' * 40}
        for outcome in ('passed', 'failed', 'skipped'):
            with self.subTest(outcome=outcome):
                result = assess([scan('pass'), scan('other', outcome, subject=other)])
                self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                self.assertTrue(any(g['kind'] == 'scan_subject_mismatch' and g['reference'] == 'other'
                                    for g in result['gaps']))
                self.assertFalse(any(g['kind'] == 'contradictory_outcome' for g in result['gaps']))
        result = assess([scan('failure', 'failed'), scan('other', subject=other)])
        self.assertEqual(result['verdict'], 'BLOCK')

    def test_invalid_persisted_subjects_require_review(self):
        malformed = {'kind': 'git_commit', 'value': 'short'}
        for claim, item, gap in ((malformed, COMMIT, 'invalid_release_subject'),
                                 (COMMIT, malformed, 'invalid_scan_subject')):
            with self.subTest(gap=gap):
                result = assess([scan('bad', 'failed', subject=item)], subject=claim)
                self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                self.assertEqual(result['subject'], COMMIT if claim == COMMIT else None)
                self.assertTrue(any(g['kind'] == gap for g in result['gaps']))
                self.assertFalse(any(g['kind'] == 'contradictory_outcome' for g in result['gaps']))

    def test_claim_subject_is_persisted_and_immutable(self):
        witness = Witness('offline', None, now=NOW)
        stored = {}
        def query(cypher, params):
            if cypher.startswith('MATCH '):
                payload = stored.get(params['id'])
                return [{'payload': payload}] if payload is not None else []
            if cypher.startswith('CREATE '):
                stored[params['id']] = params['payload']
                return []
            self.fail(f'unexpected graph query: {cypher}')
        witness.q = query
        witness.seed_claim('claim', [], subject=COMMIT)
        self.assertEqual(witness.claim_subject('claim'), COMMIT)
        witness.seed_claim('claim', [], subject=COMMIT)
        with self.assertRaises(ValueError):
            witness.seed_claim('claim', [], subject=DIGEST)
        with self.assertRaises(ValueError):
            witness.seed_claim('bad', [], subject={'kind': 'git_commit', 'value': 'short'})

    def test_scan_ingestion_rejects_malformed_subject(self):
        for subject in ({'kind': 'git_commit', 'value': 'a' * 7},
                        {'kind': 'git_commit', 'value': 'A' * 40},
                        {'kind': 'artifact_digest', 'value': 'sha256:' + 'b' * 63},
                        {'kind': 'other', 'value': 'a' * 40}):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                validate(scan('bad', subject=subject))

    def test_scan_ingestion_accepts_unset_subject_as_evidence_gap(self):
        for subject in (None, MISSING):
            with self.subTest(subject=subject):
                validate(scan('no-subject', subject=subject))

    def test_all_current_passes_approve(self):
        result = assess([scan('scan-a'), scan('scan-b')])
        self.assertEqual(result['verdict'], 'APPROVE')
        self.assertEqual(result['gaps'], [])

    def test_unknown_or_absent_outcome_requires_review_even_with_pass(self):
        for outcome in ('unknown', None, MISSING):
            with self.subTest(outcome=outcome):
                result = assess([scan('pass'), scan('uncertain', outcome)])
                self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                self.assertTrue(any(g['kind'] == 'unknown_verification_outcome'
                                    and g['reference'] == 'uncertain' for g in result['gaps']))

    def test_current_failed_or_skipped_blocks_even_with_pass(self):
        for outcome in ('failed', 'skipped'):
            with self.subTest(outcome=outcome):
                result = assess([scan('pass'), scan('adverse', outcome)])
                self.assertEqual(result['verdict'], 'BLOCK')
                self.assertIn({'kind': 'contradictory_outcome', 'reference': 'adverse',
                               'outcome': outcome}, result['gaps'])

    def test_missing_required_edge_requires_review(self):
        result = assess([scan('pass'), scan('missing')], linked={'pass'})
        self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
        self.assertTrue(any(g['kind'] == 'missing_required_artifact'
                            and g['reference'] == 'missing' for g in result['gaps']))

    def test_noncurrent_adverse_scan_requires_review_not_block(self):
        for timestamp in ('2025-12-01T00:00:00Z', '2026-01-16T00:00:00Z'):
            with self.subTest(timestamp=timestamp):
                result = assess([scan('pass'), scan('old', 'failed', observed_at=timestamp)])
                self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
                self.assertTrue(any(g['kind'] == 'stale_evidence' and g['reference'] == 'old'
                                    for g in result['gaps']))
                self.assertFalse(any(g['kind'] == 'contradictory_outcome' and g['reference'] == 'old'
                                     for g in result['gaps']))

    def test_incomplete_scan_provenance_requires_review(self):
        result = assess([scan('pass'), scan('unverified', 'failed', root_verified=False)])
        self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
        self.assertTrue(any(g['kind'] == 'incomplete_provenance' and g['reference'] == 'unverified'
                            for g in result['gaps']))
        self.assertFalse(any(g['kind'] == 'contradictory_outcome' and g['reference'] == 'unverified'
                             for g in result['gaps']))

    def test_required_edge_to_wrong_artifact_type_requires_review(self):
        result = assess([scan('pass'), scan('report', type='report')])
        self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
        self.assertIn({'kind': 'invalid_relationship', 'reference': 'report',
                       'from_source': 'ci'}, result['gaps'])


if __name__ == '__main__':
    unittest.main()
