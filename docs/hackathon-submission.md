# HydraWitness — submission draft

## Pitch

HydraWitness helps engineering and security teams check whether the evidence behind an AI-assisted release recommendation is complete. It traces reports to their sources, finds referenced missing checks, and reuses evidence relationships in later investigations.

In the synthetic demo, reports lead to a shared CI source and a required scan. The scan was skipped, so the advisory verdict changes from `REVIEW_REQUIRED` to `BLOCK`. A related investigation reuses the stored relationships. A human remains responsible for the decision.

The proposed initial customers are platform and security teams reviewing AI-assisted changes; a per-repository subscription is one possible model. Demand, willingness to pay, and pricing are not validated.

## Evidence

- A frozen, correlated synthetic held-out set improved from 10/20 correct decisions before evidence discovery to 20/20 after four learning batches. The static graph scored 10/20; a weaker flat-document heuristic scored 6/20. See [evaluation](evaluation.md).
- In a repeated synthetic investigation, stored graph relationships required 672 HydraDB queries versus 852 for reconstructing relationships from the same metadata, across 120 assessments per method. Both produced the same decisions and roots. This local workload does not prove a general speed advantage. See [repeated investigation](repeated-investigation.md).
- An artifact-only evaluator with equal access to source payloads and references matched the graph's final 20/20 accuracy. The experiment does not establish a unique graph accuracy advantage. See [ablation](ablation-report.md).
- Two saved Codex CLI sessions show an investigation and a related query in the same persisted graph scope. The dashboard video uses a separate synthetic scope.

The evidence and root-verification assertions are synthetic. The prototype is advisory, has no real source connectors, and is not a production release gate. The README documents an unresolved local-store restart problem.

## Social post draft

We built HydraWitness for the HydraDB hackathon: an advisory evidence trail for AI-assisted release decisions.

When several reports point to the same source, HydraWitness follows the chain, finds referenced missing checks, and saves those relationships for the next investigation. In our synthetic demo, a skipped scan changes the verdict from review to block.

Our small synthetic benchmark improved from 10/20 to 20/20 after discovering missing evidence. A metadata-only baseline matched final accuracy; in a separate repeated workload the stored graph used 672 queries versus 852. The repo explains the limitations.

Would your team use this to review release evidence? Which tools would it need to connect to first?

[Tag HydraDB account] [Live app link] [Repository link] [Demo link]

## Submission checklist

- [ ] Verify a publicly usable app backed by the self-hosted open-source HydraDB engine, from a separate browser.
- [ ] Publish the source under an appropriate open-source license after reviewing it for private information.
- [ ] Upload `demo/hydrawitness-final.mp4` to Loom and check sharing permissions.
- [ ] Speak with potential users and record actual feedback; do not imply demand without evidence.
- [ ] Publish the social post with the correct tag and working links.
- [ ] Submit the live app, open-source repository, and Loom before **9 AM IST, November 16, 2026**.
