# Repeated-investigation comparison

The runner `python -m evals.repeated_investigation` assesses the same 20 held-out synthetic claims with equal available source payloads in the preserved full-graph and artifact-only scopes. It creates a fresh evaluator instance for each mode on each of six rounds; the modes alternate order. All operations are read-only. Metadata mode resolves recorded references by fetching individual source nodes and reconstructs relationships on each assessment. Graph mode reads persisted `DERIVED_FROM` and `REQUIRES` adjacency. The processes, database and OS caches are shared, so these are fresh evaluator instances, not fresh database processes or separate Codex sessions.

| Metric | Persisted graph | Metadata reconstruction |
|---|---:|---:|
| Correct decisions | 120/120 | 120/120 |
| Exact root sets | 120/120 | 120/120 |
| HydraDB queries | 672 | 852 |
| Source-ID point lookups | 0 | 612 |
| Relationships reconstructed from metadata | 0 | 156 |
| Ingestion attempts | 0 | 0 |
| Per-assessment p50 | 4.96 ms | 6.23 ms |
| Per-assessment p95 | 15.05 ms | 18.91 ms |

Point lookups count direct source-ID payload queries only; graph adjacency queries also retrieve source payloads and are included in total queries. This workload records fewer requests and metadata reconstructions with stored edges. It does not establish a general latency advantage: these local measurements include HTTP and application time, a Codex session overlapped the run, caches were warm, order alternated only by round, and samples repeat correlated fixture questions. Both modes avoid ingestion because all evidence is already available. The experiment does not measure savings against a system with its own persisted cache, production-scale workloads, network latency or distributed agents. Artifact-only accuracy remains equal to the graph; materialized edges did not prove an accuracy advantage.

Results: `evals/repeated-results/results.json`. The experiment requires the preserved scopes from `evals/ablation-results/results.json`; it fails if they or the frozen benchmark are unavailable.
