"""Read-only, conservatively associated GitHub Actions evidence."""
from datetime import datetime
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .engine import COMMIT, GITHUB_ACTIONS_VERIFICATION


_REPOSITORY = re.compile(r'^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$')
_TOKEN = re.compile(r'^[A-Za-z0-9_.-]+$')
_MAX_PAGES = 10
_PAGE_SIZE = 100


def _positive_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha(value):
    return isinstance(value, str) and bool(COMMIT.fullmatch(value))


def _repository(value):
    if (not isinstance(value, str) or len(value) > 200 or not _REPOSITORY.fullmatch(value)
            or value.split('/')[1] in ('.', '..')):
        raise ValueError('invalid repository')
    return value.lower()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubActionsClient:
    def __init__(self, token=None):
        if token is not None and (not isinstance(token, str) or not _TOKEN.fullmatch(token)):
            raise ValueError('invalid GitHub token')
        self._token = token

    def _get_json(self, path, params=None):
        # Paths are constructed internally from validated values; redirects are never followed.
        url = 'https://api.github.com' + path
        if params:
            url += '?' + urlencode(params)
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'HydraWitness'}
        if self._token:
            headers['Authorization'] = 'Bearer ' + self._token
        request = Request(url, headers=headers, method='GET')
        try:
            with build_opener(_NoRedirect()).open(request, timeout=15) as response:
                content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise RuntimeError('GitHub response exceeds size limit')
            return json.loads(content)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise RuntimeError(f'GitHub request failed (HTTP {code})') from None
        except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
            raise RuntimeError('GitHub request failed or returned invalid JSON') from None

    def _list_pages(self, path, key, filters):
        records = []
        total = None
        for page in range(1, _MAX_PAGES + 1):
            data = self._get_json(path, {**filters, 'per_page': _PAGE_SIZE, 'page': page})
            if not isinstance(data, dict):
                raise RuntimeError('invalid GitHub Actions listing')
            batch, count = data.get(key), data.get('total_count')
            if not isinstance(batch, list) or type(count) is not int or count < 0 or len(batch) > _PAGE_SIZE:
                raise RuntimeError('invalid GitHub Actions listing')
            if total is None:
                total = count
            if total != count or total > _PAGE_SIZE * _MAX_PAGES:
                raise RuntimeError('incomplete or changing GitHub Actions listing')
            records.extend(batch)
            if len(records) == total:
                return records
            if len(records) > total or len(batch) != _PAGE_SIZE:
                raise RuntimeError('incomplete or inconsistent GitHub Actions listing')
        raise RuntimeError('incomplete GitHub Actions listing')

    def fetch_pr_workflows(self, repository, pull_request, *, expected_sha=None):
        repository = _repository(repository)
        if not _positive_integer(pull_request): raise ValueError('invalid pull request number')
        if expected_sha is not None and not _sha(expected_sha): raise ValueError('invalid expected SHA')
        pr = self._get_json(f'/repos/{repository}/pulls/{pull_request}')
        try:
            base_id = pr['base']['repo']['id']
            head_id = pr['head']['repo']['id']
            sha = pr['head']['sha']
            pr_number = pr['number']
        except (KeyError, TypeError):
            raise ValueError('incomplete pull request metadata') from None
        if not _positive_integer(base_id) or not _positive_integer(head_id) or not _sha(sha) or pr_number != pull_request or not _positive_integer(pr_number):
            raise ValueError('invalid pull request metadata')
        if expected_sha is not None and sha != expected_sha: raise ValueError('pull request head SHA mismatch')
        subject = {'kind':'git_commit', 'value':sha}
        records = self._list_pages(f'/repos/{repository}/actions/runs', 'workflow_runs',
                                   {'event': 'pull_request', 'head_sha': sha, 'status': 'completed'})
        artifacts = {}
        seen_runs = {}
        for run in records:
            if not isinstance(run,dict): continue
            key = (run.get('id'), run.get('run_attempt'))
            if all(_positive_integer(x) for x in key):
                if key in seen_runs:
                    if seen_runs[key] != run: raise ValueError('conflicting duplicate workflow run')
                    continue
                seen_runs[key] = run
            try:
                run_id, attempt, workflow_id = run['id'], run['run_attempt'], run['workflow_id']
                if not all(_positive_integer(x) for x in (run_id, attempt, workflow_id)): continue
                run_base, run_head = run['repository']['id'], run['head_repository']['id']
                if (run['head_sha'] != sha or run['event'] != 'pull_request' or run['status'] != 'completed'
                        or not _positive_integer(run_base) or run_base != base_id
                        or not _positive_integer(run_head) or run_head != head_id): continue
                associations = run['pull_requests']
                if not isinstance(associations,list): continue
                def matches(pr_ref):
                    if not isinstance(pr_ref,dict): return False
                    try:
                        if pr_ref['number'] != pull_request or not _positive_integer(pr_ref['number']): return False
                        association_base, association_head = pr_ref['base']['repo']['id'], pr_ref['head']['repo']['id']
                        if (not _positive_integer(association_base) or association_base != base_id
                                or not _positive_integer(association_head) or association_head != head_id): return False
                        if 'sha' in pr_ref['head'] and pr_ref['head']['sha'] != sha: return False
                        if 'head_sha' in pr_ref and pr_ref['head_sha'] != sha: return False
                        return True
                    except (KeyError, TypeError): return False
                if not any(matches(item) for item in associations): continue
                updated = run['updated_at']
                if not isinstance(updated,str) or datetime.fromisoformat(updated.replace('Z','+00:00')).tzinfo is None: continue
                conclusion = run['conclusion']
                if conclusion is not None and not isinstance(conclusion,str): continue
            except (KeyError, TypeError, ValueError):
                continue
            outcome = {'success':'passed','failure':'failed','timed_out':'failed','action_required':'failed','startup_failure':'failed','cancelled':'skipped','skipped':'skipped'}.get(conclusion,'unknown')
            artifact = {
                'external_id': f'github/{base_id}/pr/{pull_request}/run/{run_id}/attempt/{attempt}',
                'type': 'ci', 'subject': dict(subject), 'root_verified': False,
                'references': [], 'required': [], 'observed_at': updated, 'outcome': outcome,
                'source_uri': f'https://github.com/{repository}/actions/runs/{run_id}/attempts/{attempt}',
                'origin_system': 'GitHub Actions', 'issuer': 'GitHub',
                'verification_method': GITHUB_ACTIONS_VERIFICATION,
                'github_run_id': run_id, 'github_run_attempt': attempt, 'github_workflow_id': workflow_id,
                'github_status': run['status'], 'github_conclusion': conclusion,
            }
            artifacts[run_id, attempt] = artifact
        return {'repository':repository,'pull_request':pull_request,'subject':subject,'artifacts':[artifacts[key] for key in sorted(artifacts)]}
