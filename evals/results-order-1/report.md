# Synthetic learning experiment

This report is generated from live HydraDB runs; see docs/evaluation.md for protocol and limitations.

| Iteration | Accuracy | Root sets correct | False approvals | Correct reviews | Open gaps | Sources added | Relationships added |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10/20 | 16/20 | 0/14 | 10/10 | 34 | 0 | 0 |
| 1 | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 9 | 11 |
| 2 | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 0 | 0 |
| 3 | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 0 | 0 |
| 4 | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 0 | 0 |

Flat baseline accuracy: 6/20. Static baseline accuracy: 10/20.
Total: 1316 queries in 6.09s; query p50 1.51ms, p95 22.56ms.

The curve measures cross-question reuse within shared synthetic artifact groups; it does not establish transfer to unrelated organizations or documents.
