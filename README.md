# HydraWitness — graph-driven evidence improvement

HydraWitness is an advisory evidence-verification layer for engineering and security teams. It investigates whether release recommendations share origins, locates referenced missing artifacts, and persists graph repairs for later questions. The current demonstration uses synthetic evidence and provides advisory decisions; it is not a production release gate.

**Try the [live synthetic demo](https://hydrawitness-hackathon.onrender.com/).** Choose **Start walkthrough** for a guided investigation that runs the real action and explains the decision, graph, and benchmark. It runs the open-source HydraDB engine on Render's free tier. Visitors share one temporary graph; it resets when the service sleeps or restarts and can take time to wake up. If someone already ran the investigation, the graph will show the repaired state.

For a disposable Docker demo, run `docker build -t hydrawitness .` and then `docker run --rm -p 127.0.0.1:8765:8765 -e PORT=8765 -e HYDRAWITNESS_BIND=0.0.0.0 hydrawitness`. Open `http://127.0.0.1:8765`. The container keeps the synthetic graph data until it stops.

## Run the demonstration

Both the original local store and the separate recovery store returned HTTP 500 on writes after restart as of November 15, 2026. The steps below describe the demo setup but will not work reliably until a suitable storage backend or upstream fix is validated; see the recovery note below. Set `HYDRA_URL` explicitly, then install the MCP dependency once and launch a fresh dashboard scope:

```sh
export HYDRA_URL=http://127.0.0.1:18444
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m hydrawitness.launch
```

Open http://127.0.0.1:8765 and click **Investigate missing evidence**. Each tab starts with an isolated graph. **Start fresh** creates another unresolved scenario. The four reports lead to a shared CI source and a required scan for the same synthetic commit. Discovery records the skipped scan in HydraDB and changes the recommendation from `REVIEW_REQUIRED` to `BLOCK`. Click **Check stored evidence** under **Second claim** to read that decision from a different starting report in the same graph. The follow-up shows the scan finding, HydraDB read query count, and zero new ingestions or relationships.

The development container is named `hydrawitness-hydradb`, listens on localhost port 18443, and keeps data in the ignored `.hydradb` directory. Run `docker start hydrawitness-hydradb` if it is stopped. The original container setup and image digest are recorded in [the implementation log](docs/implementation-log.md). `HYDRA_URL` and `HYDRA_TOKEN` override the local development defaults. Never run against a production graph: the example writes test data and assumes a single writer.

## Design

- `hydrawitness/engine.py`: parameterized claims, scoped graph IDs, a trusted local artifact registry, gap detection, deterministic policies, iterative repair and persisted improvement records. `Witness.assess(claim_id, policy_id)` and `Witness.improve(claim_id, policy_id)` accept a policy ID from `datasets/policies.json` (a policy dictionary is also accepted for experiments).
- `datasets/controlled/`: synthetic artifacts. Reference strings are registry keys, not paths or URLs. The index rejects duplicates, unsafe references and symlinks. Artifacts explicitly list provenance references and required verification artifacts.
- `datasets/scenarios.json`: ten synthetic scenario definitions. Tests use isolated scopes and do not delete pre-existing data.
- `hydrawitness/proof.py`: the original fixed-ID proof, retained for historical compatibility. Its simplified root counting is **not** the new engine and is unsuitable for evidence decisions.

The engine stores source payloads, claims, relationships and each repair iteration in HydraDB. It follows `SUPPORTS`, `DERIVED_FROM` and `REQUIRES` edges using parameterized directed queries, verifies graph edges against declared references, and checks roots explicitly. Cycles are invalid. Missing references, depth limits, stale sources and unverified leaves require review. The controlled fixtures supply the `root_verified` assertion. Sources are immutable within a scope. Policy decisions are advisory.

### Release identity

Seed the claim with `Witness.seed_claim(claim_id, source_refs, subject=subject)` and include a `subject` object in each scan artifact. The supported forms are:

```json
[
  {"kind": "git_commit", "value": "fca3fba3c16359e6a89a77d0333a2e25a4d1ad9f"},
  {"kind": "artifact_digest", "value": "sha256:29002960b044228f1ad068e648c854cce25b95fd2e7669256b3f8c34c8abb050"}
]
```

Git commit IDs use 40 or 64 lowercase hex digits. Artifact digests use `sha256:` followed by 64 lowercase hex digits. The claim subject comes from the configured seeding process and is immutable. For a policy requiring scans, every required scan must be current, pass, and match the claim subject exactly. A current matching failure or skip blocks. Missing, invalid, and mismatched identities produce evidence gaps and require review if there is no matching result that blocks. Identity matching compares recorded metadata. Verifying the issuer and the artifact itself requires independent evidence.

Claims and scans seeded before subject binding remain readable. To assess the updated demo fixtures, use a fresh scope so the new subjects can be seeded alongside the existing records.

### Scan invalidation impact

After investigating the demo, select `demo/scan` under **Scan impact preview**. The result lists `checkout-deployment` and `checkout-security` with a shortest recorded dependency path for each. In Codex, call `scan_impact` with `scan_id: "demo/scan"` in the same scope.

The read-only preview follows declared `REQUIRES` and `DERIVED_FROM` relationships back to `SUPPORTS` links within the assessment depth limit. It flags claims for reassessment when their exact release identity matches the scan.

### GitHub Actions observations

The local connector reads pull request metadata and completed GitHub Actions workflow runs using GET requests only. For private repositories, set `GITHUB_TOKEN` to a token with **Pull requests: read** and **Actions: read** access for the repository. Public repositories can be read without a token, subject to GitHub rate limits. The connector requires an explicit PR association on each run. Some fork runs lack that association. [GitHub pull request API](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request) · [GitHub Actions API](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository)

```sh
# Preview the actual GitHub response as normalized evidence without graph writes.
python -m hydrawitness.import_github_actions OWNER/REPO 123 --scope my-scope --claim my-release --expected-sha FULL_COMMIT_SHA --dry-run
# Import into a claim in the specified graph scope.
python -m hydrawitness.import_github_actions OWNER/REPO 123 --scope my-scope --claim my-release --expected-sha FULL_COMMIT_SHA
```

The optional `--expected-sha` requires an exact match to the full PR head commit before ingestion. The JSON result includes the commit, scope, normalized artifacts, and source IDs. Imports with matching runs create a claim for that commit or reuse an existing claim with the same commit. Completed workflow attempts have immutable identities, and repeat imports deduplicate them. Set `HYDRAWITNESS_SCOPE` to the import scope to read the records through MCP `verify_evidence` and `trace_sources` in `provenance.workflow_evidence`. The release policy evaluates required security scans separately from these GitHub-reported CI observations. Proving the exact checkout or artifact produced by a workflow requires additional evidence.

## Scope and limitations

The prototype has no cryptographic verification, transactional ingestion, concurrent-writer protection, source supersession, full temporal or contradiction semantics, or general natural-language claim extraction. The policy model covers only the rules implemented here; it is not a production security policy. Required scans are associated through explicit artifact references, not inferred from text. A missing artifact without a recorded reference is reported but cannot be fetched automatically. Improvement records are persisted but there is no history browsing API. Each demo and test leaves isolated synthetic data in the development graph. HydraDB errors propagate and results requiring pagination are rejected rather than treated as complete.

A synthetic held-out benchmark, local dashboard and Codex MCP integration are available. A broader independent benchmark and graph integrity hardening remain necessary. HydraDB stores the evidence, provenance and repairs used by this implementation. A separate artifact-only evaluator reconstructed the same relationships from metadata and matched its accuracy; the graph-specific accuracy advantage remains unproven. The intended buyers are engineering, security and platform teams making high-impact AI-assisted decisions. Demand and pricing remain unvalidated. A possible commercial model is an organization subscription or usage-based pricing per verified decision; no customer revenue is claimed.

## Reproducible learning benchmark

The frozen synthetic dataset has 40 learning and 20 held-out questions. The recorded run improved from 10/20 to 20/20 across four learning batches, with a 10/20 static graph and 6/20 flat baseline. These measurements predate release-subject binding. The benchmark and challenge fixtures omit release identities, so current mandatory-scan assessments can return review where historical labels expect approval or block. Use revision `6383373` to reproduce the recorded experiments. [Evaluation methodology and reproduction details](docs/evaluation.md) [Generated report](evals/results/report.md) [JSON](evals/results/results.json) [CSV](evals/results/iterations.csv) [Accuracy chart](evals/results/accuracy.svg)

A subsequent [artifact-only ablation and separate manual challenge](docs/ablation-report.md) found that the artifact-only method matched the full graph's 20/20 decision and root accuracy when given the same documents and their references. The new challenge improved from 7/10 to 10/10 after repairing those same cases. Both are small synthetic experiments. The [Codex MCP integration](docs/mcp-integration-spec.md) has been exercised by two real Codex CLI sessions; the JSONL captures are in `demo/`.


## Codex MCP and tests

To use the MCP integration, configure a trusted Codex project to run `.venv/bin/python -m hydrawitness.mcp_server` and pass `HYDRA_URL`, `HYDRA_TOKEN`, and `HYDRAWITNESS_SCOPE` through the environment. The launch command prints `HYDRAWITNESS_SCOPE`; export that value in a shell before starting Codex from this directory. Ask the agent to use `verify_evidence` on `checkout-deployment`, then `assess_and_improve`. A new session using the same scope can call `verify_evidence` on `checkout-security`. Scope and policy are controlled by server configuration; the tools are advisory and do not deploy. The repository contains two [actual Codex session traces](demo/codex-session-1.jsonl) (the second is `demo/codex-session-2.jsonl`). Unrelated Waggle events were removed; HydraWitness calls and agent messages remain unchanged. The captures use two source reports, while the newer dashboard uses four.

GitHub Actions runs **Offline tests** and **HydraDB integration** as independent jobs for pull requests. Both jobs use Python 3.14 and install `requirements.txt`. Integration starts a fresh HydraDB 0.4.0 container on a temporary loopback port and removes it when the suite exits. [CI workflow](.github/workflows/ci.yml)

Run the same suites locally from the repository root. The integration command requires Docker.

```sh
.venv/bin/python -m tests.suites offline
PYTHON=.venv/bin/python sh scripts/test-with-hydradb.sh
```

Use `@integration_test` from `tests` on a test method or class that requires live HydraDB. Standard unittest discovery runs both suites when a test instance is configured. The repeated-investigation report records 672 graph requests and 852 metadata reconstruction requests across 120 assessments per mode before subject binding. [Repeated-investigation report](docs/repeated-investigation.md) [Demo script](docs/demo-script.md)

To run a new pair of actual Codex sessions, with the Codex CLI authenticated and project MCP config trusted, use `.venv/bin/python demo/run_codex.py`. It seeds a fresh shared scope and writes filtered real JSONL events under `demo/runs/<scope>/`. It requires model access for Codex; no paid external model API is required by HydraWitness itself.

## Local storage recovery note

On 2026-11-14 the original local-filesystem HydraDB store began returning HTTP 500 after restart; its log reported `PutMode::Update` is not implemented by `LocalFileSystem`. The original `.hydradb/store` and its graph data remain in place. The [upstream issue](https://github.com/hydra-db/hydradb/issues/81) describes a related local-store limitation. Do not delete or reset that store to recover it.

A separate disposable HydraDB node was started on `127.0.0.1:18444` using `.hydradb/recovery/store`. On November 15, after restarting that node, its store also failed writes with the same unsupported `PutMode::Update` operation. `scripts/start-recovery.sh` does not fix this error. Both stores and the saved experiment results remain preserved. Historical scopes from the original node are not present in the recovery store; runners that depend on those scopes cannot be reproduced against it without rebuilding the original experiment. An S3-compatible object store or a verified upstream fix should be evaluated before relying on restart persistence.

## Submission demo

A 2:10 final walkthrough was recorded locally and is awaiting upload. It combines a recording of a real dashboard investigation with labeled replays of two saved Codex CLI sessions. The dashboard and Codex traces use different synthetic graph scopes. Narration was generated using a local system voice; no deployment is performed in the recording. Video and raw recordings are excluded from this repository.

To capture a new silent browser recording, install optional recording dependencies with `.venv/bin/pip install playwright==1.65.2` and `.venv/bin/python -m playwright install ffmpeg`, then run `scripts/record-demo.sh`. It starts its own dashboard on port 8766 with a new recovery-store scope, records a real graph repair, and stops only the server it started. It replays the saved actual Codex events; use `.venv/bin/python demo/run_codex.py` for new real sessions. This recording script assumes Google Chrome is installed at the standard macOS path.
