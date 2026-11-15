# Artifact-only ablation and topology challenge

## Evidence coverage versus persisted provenance edges

The controlled benchmark compares the same 20 frozen held-out questions and policies. The full graph is the preserved final scope from the prior frozen-order run. The static values are that run's original pre-learning evaluation. The artifact-only scope contains the same 21 available source payloads as the final full graph: 12 initially available artifacts plus the exact nine newly discovered source artifacts. Payload equality across both HydraDB scopes was checked. It has the necessary claim-to-source `SUPPORTS` edges and **no** `DERIVED_FROM` or `REQUIRES` edges. It uses the same policy/lineage assessment code but resolves each referenced source directly by its recorded identifier at query time; it can inspect all available document content and metadata. No unrestricted external paths or uningested registry artifacts are consulted.

| Configuration | Decision accuracy | Exact root sets | False approvals | Correct review | Remaining gap records | Evaluation queries | Query p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static graph | 10/20 | 16/20 | 0/14 | 10/10 | 34 | 88 | 1.66 ms |
| Artifact-only | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 142 | 1.26 ms |
| Full HydraWitness | 20/20 | 20/20 | 0/14 | 10/10 | 16 | 112 | 1.75 ms |

The artifact-only method matches the full graph's individual decisions and root sets. **This experiment does not show an accuracy benefit from persisting graph edges beyond making the same artifacts and explicit references available.** The full graph used 30 fewer evaluation queries than artifact-only in this particular run. Latencies are client-side single-run measurements from different times, without a controlled load or repeated timing experiment; they do not establish a speedup. Static figures were preserved from the previous run, not remeasured in this comparison. The full graph query counts and latency were freshly read from the preserved graph. The earlier flat baseline was 6/20; it is a weaker document heuristic and is not the artifact-only baseline.

The 10-point improvement comes from five pairs of related questions acquiring missing referenced CI, scan or root artifacts and their corresponding validated dependency information. The graph stores `DERIVED_FROM` and `REQUIRES` relationships so a subsequent question sharing a source can follow them without another ingestion. The ablation shows that an equally capable evaluator can reconstruct those relationships from the same available metadata; it does not isolate or prove a decision-quality gain from materializing edges. There is no artifact-only checkpoint curve: this is a final-checkpoint comparison, while the preserved learning curve in `evals/results/accuracy.svg` remains unchanged. No label was adjusted after outcomes were observed.

## Separately authored challenge

The manually authored topology challenge was created and checksummed before execution. Ten individually specified questions use ten structures, including a diamond, two- and three-origin branches, a cycle with a verified side branch, partially missing branches, an old upstream root, an old required scan, opposing required scans, an optional failed scan and separate complete/incomplete supports. These are new synthetic examples, not an external dataset or independent expert review. Their root flags are trusted fixture assertions. Questions still use preselected claim and source IDs; no natural-language generalization is measured.

| Assessment | Decision accuracy | Exact root sets | False approvals | Unanswered gap records |
|---|---:|---:|---:|---:|
| Initial graph | 7/10 | 7/10 | 0/8 | 18 |
| After assessing and repairing the same cases | 10/10 | 10/10 | 0/8 | 8 |

Repair added 18 source nodes and 20 evidence edges with 295 HydraDB queries. Three decisions changed from review to the labeled outcome; no initially correct decision worsened. This is **same-case improvement**, not held-out transfer. Remaining gaps represent stale, missing, cyclic or contradictory evidence; a correct review does not require those gaps to disappear. The ten controlled benchmark evidence groups and ten manually authored challenge structures are the useful scale of evidence, not 30 independent production examples. Their accuracies should not be combined.

## Robustness and remaining uncertainty

Eleven live tests pass, including reversing question order and gap/evidence ingestion order, shared origins, unrelated outcomes in the preserved benchmark, missing references, cycles, incomplete multi-parent provenance, repeated ingestion, rejected mutations during read-only assessment, registry integrity and failed database queries. The preserved benchmark's two orderings yielded different checkpoint curves but the same final score. No observed verdict became incorrect during the measured transitions. This is limited ordering coverage, not exhaustive concurrency, fault-injection or resilience testing. No new engine correctness defect was demonstrated in this phase.

The existing claim scorer still supports only a narrow explicit policy model and source metadata; it does not prove authenticity, infer arbitrary contradictions, handle policy supersession, perform natural-language claim extraction, or protect concurrent writes transactionally. The benchmark questions were partially derived from earlier fixtures, and challenge authors knew the system design. Further independent labels, unseen data, source authority validation and a stronger adversarial evaluation remain necessary.

Reproduce with `python3 -m evals.ablation`, `python3 -m evals.challenge`, `python3 -m evals.render_comparisons`, and `python3 -m unittest discover -s tests -v`. The ablation depends on the preserved full graph scope named in `evals/results/results.json`; it fails rather than silently recreating that graph if it no longer matches. Each experiment adds isolated data and does not delete existing graph records.
