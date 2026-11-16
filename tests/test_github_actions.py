"""Offline GitHub Actions import and workflow evidence regression tests."""
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from hydrawitness.engine import Witness
from hydrawitness.github_actions import GitHubActionsClient
from hydrawitness.import_github_actions import main as import_workflows


SHA = 'a' * 40
SUBJECT = {'kind': 'git_commit', 'value': SHA}


def artifact(ref='github/run/1/attempt/1', **changes):
    item = {'external_id': ref, 'type': 'ci', 'subject': SUBJECT.copy(),
            'observed_at': '2026-01-01T00:00:00Z', 'root_verified': False,
            'references': [], 'required': [], 'verification_method': 'github_actions_rest'}
    item.update(changes)
    return item


class MemoryWitness(Witness):
    def __init__(self):
        super().__init__('test', None, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.nodes = {}
        self.edges = set()
        self.writes = 0

    def node(self, label, key, payload):
        ident = self.nid(label, key)
        value = copy.deepcopy(payload)
        if (label, ident) in self.nodes:
            if self.nodes[label, ident] != value:
                raise ValueError('immutable identity conflict')
            return ident, False
        self.nodes[label, ident] = value
        self.writes += 1
        return ident, True

    def edge(self, a_label, a, kind, b_label, b):
        edge = (a_label, a, kind, b_label, b)
        if edge in self.edges:
            return False
        self.edges.add(edge)
        self.writes += 1
        return True

    def q(self, cypher, params=None):
        if not cypher.startswith('MATCH ') or 'CI_EVIDENCE_FOR' not in cypher:
            raise AssertionError(f'unexpected query: {cypher}')
        claim_id = params['id']
        claim = self.nodes.get(('Claim', claim_id))
        if claim is None:
            return []
        return [{'id': src_id, 'payload': json.dumps(self.nodes['Source', src_id]),
                 'claim': json.dumps(claim)}
                for label, src_id, relation, target_label, target_id in self.edges
                if label == 'Source' and relation == 'CI_EVIDENCE_FOR'
                and target_label == 'Claim' and target_id == claim_id]


class WorkflowIngestionTests(unittest.TestCase):
    def test_ingest_readback_and_repeat_are_idempotent(self):
        witness = MemoryWitness()
        observation = artifact()
        first = witness.ingest_workflow_evidence('claim', SUBJECT, [observation])
        second = witness.ingest_workflow_evidence('claim', SUBJECT, [observation])
        self.assertEqual(first, {'sources_ingested': 1, 'edges_added': 1})
        self.assertEqual(second, {'sources_ingested': 0, 'edges_added': 0})
        self.assertEqual(witness.workflow_evidence('claim'), [observation])
        self.assertEqual({edge[2] for edge in witness.edges}, {'CI_EVIDENCE_FOR'})

    def test_invalid_artifacts_rejected_before_any_write(self):
        invalid = [artifact(type='security_scan'), artifact(subject=None),
                   artifact(subject={'kind': 'git_commit', 'value': 'b' * 40})]
        missing = artifact()
        del missing['subject']
        invalid.append(missing)
        for item in invalid:
            with self.subTest(item=item):
                witness = MemoryWitness()
                with self.assertRaises(ValueError):
                    witness.ingest_workflow_evidence('claim', SUBJECT, [artifact(), item])
                self.assertEqual(witness.writes, 0)

    def test_changed_subject_conflicts_with_existing_claim(self):
        witness = MemoryWitness()
        witness.ingest_workflow_evidence('claim', SUBJECT, [artifact()])
        before = witness.writes
        different = {'kind': 'git_commit', 'value': 'b' * 40}
        with self.assertRaises(ValueError):
            witness.ingest_workflow_evidence('claim', different, [artifact(subject=different)])
        self.assertEqual(witness.writes, before)

    def test_ci_observation_cannot_satisfy_security_scan_policy(self):
        witness = MemoryWitness()
        witness.ingest_workflow_evidence('claim', SUBJECT, [artifact()])
        witness.claim_subject = lambda claim: SUBJECT
        witness.attached = lambda claim: []
        result = witness.assess('claim', {'id': 'release', 'min_roots': 1,
                                          'require_security_scan': True})
        self.assertEqual(result['verdict'], 'REVIEW_REQUIRED')
        self.assertTrue(any(g['kind'] == 'missing_mandatory_verification' for g in result['gaps']))
        self.assertEqual(result['supporting_documents'], 0)


def association():
    return {'number': 7, 'base': {'repo': {'id': 10}},
            'head': {'repo': {'id': 20}, 'sha': SHA}}


def run(run_id=1, attempt=1, **changes):
    item = {'id': run_id, 'run_attempt': attempt, 'workflow_id': 11, 'head_sha': SHA,
            'event': 'pull_request', 'status': 'completed', 'repository': {'id': 10},
            'head_repository': {'id': 20}, 'pull_requests': [association()],
            'updated_at': '2026-01-01T00:00:00Z', 'conclusion': 'success'}
    item.update(changes)
    return item


class FakeGitHub(GitHubActionsClient):
    def __init__(self, runs, *, head=SHA):
        super().__init__()
        self.runs = runs
        self.head = head
        self.calls = []

    def _get_json(self, path, params=None):
        self.calls.append((path, params))
        if '/pulls/' in path:
            result = association()
            result['head']['sha'] = self.head
            return result
        page = params['page']
        return {'total_count': len(self.runs), 'workflow_runs': self.runs[(page-1)*100:page*100]}


class GitHubActionsAdapterTests(unittest.TestCase):
    def test_only_completed_correctly_associated_pr_head_runs_are_imported(self):
        wrong_pr = association()
        wrong_pr['number'] = 8
        wrong_repo = association()
        wrong_repo['head']['repo']['id'] = 21
        wrong_assoc_sha = association()
        wrong_assoc_sha['head']['sha'] = 'b' * 40
        runs = [run(), run(2, head_sha='b' * 40), run(3, event='push'),
                run(4, status='in_progress'), run(5, pull_requests=[]),
                run(6, pull_requests=[wrong_pr]), run(7, pull_requests=[wrong_repo]),
                run(8, repository={'id': 999}), run(9, head_repository={'id': 999}),
                run(10, pull_requests=[wrong_assoc_sha])]
        result = FakeGitHub(runs).fetch_pr_workflows('owner/repo', 7, expected_sha=SHA)
        self.assertEqual(result['subject'], SUBJECT)
        self.assertEqual([a['github_run_id'] for a in result['artifacts']], [1])
        self.assertEqual(result['repository'], 'owner/repo')
        self.assertEqual(result['pull_request'], 7)
        with self.assertRaises(ValueError):
            FakeGitHub(runs).fetch_pr_workflows('owner/repo', 7, expected_sha='b' * 40)

    def test_adapter_output_ingests_and_reads_back(self):
        result = FakeGitHub([run()]).fetch_pr_workflows('owner/repo', 7)
        witness = MemoryWitness()
        self.assertEqual(witness.ingest_workflow_evidence('claim', result['subject'], result['artifacts']),
                         {'sources_ingested': 1, 'edges_added': 1})
        self.assertEqual(witness.workflow_evidence('claim'), result['artifacts'])

    def test_conclusions_and_attempt_ids(self):
        conclusions = ['success', 'failure', 'timed_out', 'cancelled', 'skipped', None, 'neutral']
        client = FakeGitHub([run(123, index, conclusion=conclusion)
                             for index, conclusion in enumerate(conclusions, 1)])
        items = client.fetch_pr_workflows('owner/repo', 7)['artifacts']
        self.assertEqual([a['outcome'] for a in items],
                         ['passed', 'failed', 'failed', 'skipped', 'skipped', 'unknown', 'unknown'])
        self.assertEqual(len({a['external_id'] for a in items}), len(items))
        self.assertEqual(items, client.fetch_pr_workflows('owner/repo', 7)['artifacts'])
        self.assertTrue(all(a['type'] == 'ci' and a['subject'] == SUBJECT for a in items))

    def test_pagination_and_incomplete_listing(self):
        client = FakeGitHub([run(index) for index in range(1, 102)])
        self.assertEqual(len(client.fetch_pr_workflows('owner/repo', 7)['artifacts']), 101)
        self.assertEqual([params['page'] for path, params in client.calls if params], [1, 2])
        class Incomplete(FakeGitHub):
            def _get_json(self, path, params=None):
                if params:
                    return {'total_count': 101, 'workflow_runs': [run()]}
                return super()._get_json(path, params)
        with self.assertRaises(RuntimeError):
            Incomplete([]).fetch_pr_workflows('owner/repo', 7)

    def test_http_failure_is_sanitized(self):
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 403, 'secret-token', {}, None)
        with patch('hydrawitness.github_actions.build_opener', return_value=Opener()):
            with self.assertRaises(RuntimeError) as error:
                GitHubActionsClient(token='secret-token').fetch_pr_workflows('owner/repo', 7)
        self.assertNotIn('secret-token', str(error.exception))

    def test_conflicting_duplicate_attempt_fails_closed(self):
        with self.assertRaises(ValueError):
            FakeGitHub([run(), run(conclusion='failure')]).fetch_pr_workflows('owner/repo', 7)


class WorkflowImportCLITests(unittest.TestCase):
    def test_dry_run_and_empty_results_do_not_create_a_claim(self):
        arguments = ['owner/repo', '7', '--scope', 'test-scope', '--claim', 'release',
                     '--expected-sha', SHA]
        for runs, args in (([run()], arguments + ['--dry-run']), ([], arguments)):
            with self.subTest(runs=runs), StringIO() as output, redirect_stdout(output):
                with patch('hydrawitness.import_github_actions.GitHubActionsClient', return_value=FakeGitHub(runs)):
                    with patch('hydrawitness.import_github_actions.Witness') as witness:
                        self.assertEqual(import_workflows(args), 0)
                witness.assert_not_called()
                summary = json.loads(output.getvalue())
                self.assertEqual(summary['subject'], SUBJECT)
                self.assertEqual(summary['sources_ingested'], 0)
                self.assertEqual(len(summary['artifacts']), len(runs))
