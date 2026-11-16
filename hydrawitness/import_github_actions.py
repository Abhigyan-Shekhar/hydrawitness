"""Import GitHub Actions pull-request observations into a scoped HydraWitness graph."""
import argparse
import json
import os
import re
import sys

from .engine import COMMIT, Witness
from .github_actions import GitHubActionsClient


def _claim(value):
    if len(value) > 120 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]*', value):
        raise argparse.ArgumentTypeError('must be an identifier of at most 120 characters')
    return value


def _scope(value):
    if not value or not value.strip():
        raise argparse.ArgumentTypeError('must be non-empty')
    return value


def _pull_request(value):
    if not value.isascii() or not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError('must be a positive pull request number')
    return int(value)


def _sha(value):
    if not COMMIT.fullmatch(value):
        raise argparse.ArgumentTypeError('must be a full lowercase 40- or 64-character commit SHA')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', metavar='OWNER/REPO')
    parser.add_argument('pull_request', type=_pull_request, metavar='PR')
    parser.add_argument('--scope', required=True, type=_scope)
    parser.add_argument('--claim', required=True, type=_claim)
    parser.add_argument('--expected-sha', type=_sha)
    parser.add_argument('--dry-run', action='store_true', help='fetch and preview evidence without graph writes')
    args = parser.parse_args(argv)

    try:
        result = GitHubActionsClient(token=os.getenv('GITHUB_TOKEN') or None).fetch_pr_workflows(
            args.repository, args.pull_request, expected_sha=args.expected_sha)
    except (ValueError, RuntimeError) as exc:
        print(f'GitHub evidence fetch failed: {exc}', file=sys.stderr)
        return 1

    artifacts = result['artifacts']
    ingestion = {'sources_ingested': 0, 'edges_added': 0}
    if artifacts and not args.dry_run:
        try:
            ingestion = Witness(args.scope, None).ingest_workflow_evidence(args.claim, result['subject'], artifacts)
        except Exception:
            print('HydraDB ingestion failed; check the claim, scope, subject and database connection.', file=sys.stderr)
            return 1
    print(json.dumps({
        'repository': result['repository'], 'pull_request': result['pull_request'],
        'scope': args.scope, 'claim_id': args.claim, 'subject': result['subject'],
        'artifacts': artifacts, 'source_ids': [item['external_id'] for item in artifacts],
        'sources_ingested': ingestion['sources_ingested'], 'edges_added': ingestion['edges_added'],
        'dry_run': args.dry_run,
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
