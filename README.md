# HydraWitness — graph-driven evidence improvement

HydraWitness is an advisory evidence-verification layer for engineering and security teams. It investigates whether release recommendations share origins, locates referenced missing artifacts, and persists graph repairs for later questions. The current demonstration uses synthetic evidence and provides advisory decisions; it is not a production release gate.

For a disposable Docker demo, run `docker build -t hydrawitness .` and then `docker run --rm -p 127.0.0.1:8765:8765 -e PORT=8765 -e HYDRAWITNESS_BIND=0.0.0.0 hydrawitness`. Open `http://127.0.0.1:8765`. The Render free demo starts a fresh synthetic graph on each service start; visitors share it, and all changes disappear on restart. Do not use it for sensitive data.

## Run the demonstration

Both the original local store and the separate recovery store returned HTTP 500 on writes after restart as of November 15, 2026. The steps below describe the demo setup but will not work reliably until a suitable storage backend or upstream fix is validated; see the recovery note below. Set `HYDRA_URL` explicitly, then install the MCP dependency once and launch a fresh dashboard scope:

```sh
export HYDRA_URL=http://127.0.0.1:18444
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m hydrawitness.launch
```

Open http://127.0.0.1:8765, then click **Investigate missing evidence**. The dashboard creates a new isolated scope on every launch; it never clears the existing graph. Its question starts with four reports. Their recorded references lead to a shared CI source and then to a required scan. The resolver looks up those references in `datasets/controlled`, validates the artifacts, and writes the resulting nodes and edges to HydraDB. The synthetic scan says it was skipped, so the policy changes from `REVIEW_REQUIRED` to `BLOCK`. A related question uses the persisted relationships, returns `BLOCK` immediately, and performs no additional ingestion. The output includes actual query and write counts and the iteration history. These scenarios are synthetic, and this one example does not establish generalization or an accuracy improvement.

The development container is named `hydrawitness-hydradb`, listens on localhost port 18443, and keeps data in the ignored `.hydradb` directory. Run `docker start hydrawitness-hydradb` if it is stopped. The original container setup and image digest are recorded in [the implementation log](docs/implementation-log.md). `HYDRA_URL` and `HYDRA_TOKEN` override the local development defaults. Never run against a production graph: the example writes test data and assumes a single writer.

## Design

- `hydrawitness/engine.py`: parameterized claims, scoped graph IDs, a trusted local artifact registry, gap detection, deterministic policies, iterative repair and persisted improvement records. `Witness.assess(claim_id, policy_id)` and `Witness.improve(claim_id, policy_id)` accept a policy ID from `datasets/policies.json` (a policy dictionary is also accepted for experiments).
- `datasets/controlled/`: synthetic artifacts. Reference strings are registry keys, not paths or URLs. The index rejects duplicates, unsafe references and symlinks. Artifacts explicitly list provenance references and required verification artifacts.
- `datasets/scenarios.json`: ten synthetic scenario definitions. Tests use isolated scopes and do not delete pre-existing data.
- `hydrawitness/proof.py`: the original fixed-ID proof, retained for historical compatibility. Its simplified root counting is **not** the new engine and is unsuitable for evidence decisions.

The engine stores source payloads, claims, relationships and each repair iteration in HydraDB. It follows `SUPPORTS`, `DERIVED_FROM` and `REQUIRES` edges using parameterized directed queries, verifies graph edges against declared references, and checks roots explicitly. Cycles are invalid; missing references, depth limits, stale sources and unverified leaves require review. A current, explicitly verified linked scan reporting `skipped` or `failed` blocks; a missing scan requires review. A root's `root_verified` flag is an assertion supplied by the controlled fixture, not independent real-world verification. Sources are immutable within a scope: conflicting content for the same ID raises an error. Policy decisions are advisory.

## Scope and limitations

The prototype has no real source connectors, authentication or cryptographic verification, transactional ingestion, concurrent-writer protection, source supersession, full temporal or contradiction semantics, or general natural-language claim extraction. The policy model covers only the rules implemented here; it is not a production security policy. Required scans are associated through explicit artifact references, not inferred from text. A missing artifact without a recorded reference is reported but cannot be fetched automatically. Improvement records are persisted but there is no history browsing API. Each demo and test leaves isolated synthetic data in the development graph. HydraDB errors propagate and results requiring pagination are rejected rather than treated as complete.

A synthetic held-out benchmark, local dashboard and Codex MCP integration are available. A broader independent benchmark and graph integrity hardening remain necessary. HydraDB stores the evidence, provenance and repairs used by this implementation. A separate artifact-only evaluator reconstructed the same relationships from metadata and matched its accuracy; the graph-specific accuracy advantage remains unproven. The intended buyers are engineering, security and platform teams making high-impact AI-assisted decisions. Demand and pricing remain unvalidated. A possible commercial model is an organization subscription or usage-based pricing per verified decision; no customer revenue is claimed.

## Reproducible learning benchmark

Run `python3 -m evals.run` against the local HydraDB container. The frozen synthetic dataset has 40 learning and 20 held-out questions; each run uses a new graph scope and adds data without deleting existing records. The measured default run improved from 10/20 to 20/20 across four learning batches, with a 10/20 static graph and 6/20 flat baseline. These are highly correlated synthetic questions sharing artifacts, not a production accuracy estimate. [Evaluation methodology and reproduction details](docs/evaluation.md) explain the labels, read-only evaluation, baseline limitations, ordering repeat, query counts and disk implications. Results are in [the generated report](evals/results/report.md), [JSON](evals/results/results.json), [CSV](evals/results/iterations.csv), and [accuracy chart](evals/results/accuracy.svg).

A subsequent [artifact-only ablation and separate manual challenge](docs/ablation-report.md) found that the artifact-only method matched the full graph's 20/20 decision and root accuracy when given the same documents and their references. The new challenge improved from 7/10 to 10/10 after repairing those same cases. Both are small synthetic experiments. The [Codex MCP integration](docs/mcp-integration-spec.md) has been exercised by two real Codex CLI sessions; the JSONL captures are in `demo/`.


## Codex MCP and tests

The repository-scoped `.codex/config.toml` configures the real stdio MCP server for trusted projects. The launch command prints `HYDRAWITNESS_SCOPE`; export that value in a shell before starting Codex from this directory. Ask the agent to use `verify_evidence` on `checkout-deployment`, then `assess_and_improve`. A new session using the same scope can call `verify_evidence` on `checkout-security`. Scope and policy are controlled by server configuration; the tools are advisory and do not deploy. The repository contains two [actual Codex session traces](demo/codex-session-1.jsonl) (the second is `demo/codex-session-2.jsonl`). Unrelated Waggle events were removed; HydraWitness calls and agent messages remain unchanged. The captures use two source reports, while the newer dashboard uses four.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m evals.repeated_investigation
```

The [repeated-investigation report](docs/repeated-investigation.md) describes a local alternating-order experiment: both modes returned the same answers, with 672 graph requests versus 852 for metadata reconstruction across 120 assessments each. That single local workload is not proof of a general speed advantage. The [demo script](docs/demo-script.md) explains how to present the actual findings.

To run a new pair of actual Codex sessions, with the Codex CLI authenticated and project MCP config trusted, use `.venv/bin/python demo/run_codex.py`. It seeds a fresh shared scope and writes filtered real JSONL events under `demo/runs/<scope>/`. It requires model access for Codex; no paid external model API is required by HydraWitness itself.

## Local storage recovery note

On 2026-11-14 the original local-filesystem HydraDB store began returning HTTP 500 after restart; its log reported `PutMode::Update` is not implemented by `LocalFileSystem`. The original `.hydradb/store` and its graph data remain in place. The [upstream issue](https://github.com/hydra-db/hydradb/issues/81) describes a related local-store limitation. Do not delete or reset that store to recover it.

A separate disposable HydraDB node was started on `127.0.0.1:18444` using `.hydradb/recovery/store`. On November 15, after restarting that node, its store also failed writes with the same unsupported `PutMode::Update` operation. `scripts/start-recovery.sh` does not fix this error. Both stores and the saved experiment results remain preserved. Historical scopes from the original node are not present in the recovery store; runners that depend on those scopes cannot be reproduced against it without rebuilding the original experiment. An S3-compatible object store or a verified upstream fix should be evaluated before relying on restart persistence.

## Submission demo

The [2:10 final cut](demo/hydrawitness-final.mp4) and [2:33 earlier draft](demo/hydrawitness-submission-draft.mp4) combine a slowed recording of a real dashboard investigation with clearly labeled replays of two saved real Codex CLI sessions. The dashboard and Codex traces use different synthetic graph scopes. Narration was generated using the local system voice. The [50-second silent capture](demo/hydrawitness-demo-draft.mp4) is also retained. Neither video performs a production deployment.

To capture a new silent browser recording, install optional recording dependencies with `.venv/bin/pip install playwright==1.65.2` and `.venv/bin/python -m playwright install ffmpeg`, then run `scripts/record-demo.sh`. It starts its own dashboard on port 8766 with a new recovery-store scope, records a real graph repair, and stops only the server it started. It replays the saved actual Codex events; use `.venv/bin/python demo/run_codex.py` for new real sessions. This recording script assumes Google Chrome is installed at the standard macOS path.
