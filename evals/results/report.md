# Synthetic learning experiment

This report is generated from live HydraDB runs; see docs/evaluation.md for protocol and limitations.

| Iteration | Accuracy | Root sets correct | False approvals | Correct reviews | Open gaps | Sources added | Relationships added |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10/20 | 16/20 | 0/14 | 10/10 | 34 | 0 | 0 |
| 1 | 14/20 | 18/20 | 0/14 | 10/10 | 26 | 3 | 4 |
| 2 | 14/20 | 18/20 | 0/14 | 10/10 | 26 | 0 | 0 |
| 3 | 16/20 | 18/20 | 0/14 | 10/10 | 22 | 3 | 4 |
| 4 | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 3 | 3 |

Flat baseline accuracy: 6/20. Static baseline accuracy: 10/20.
Total: 1284 queries in 5.81s; query p50 1.44ms, p95 22.22ms.

The curve measures cross-question reuse within shared synthetic artifact groups; it does not establish transfer to unrelated organizations or documents.
