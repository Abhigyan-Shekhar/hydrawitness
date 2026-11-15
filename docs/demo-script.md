# HydraWitness demo script

All evidence is synthetic; the release recommendation is advisory. No production deployment is performed.

1. Start the dashboard using the README. A fresh scoped graph begins with four apparently supportive documents and a `REVIEW_REQUIRED` decision. The graph shows only known edges; missing references are visible as gaps.
2. Select **Investigate missing evidence**. HydraWitness follows recorded references, fetches the CI summary and skipped scan from the controlled registry, and writes validated `DERIVED_FROM` and `REQUIRES` relationships to HydraDB. The decision becomes `BLOCK` under the required-scan policy. Show the actual source, edge and query counts.
3. Explain that a missing scan alone requires review; a verified skipped mandatory scan causes block. Show the two real Codex CLI sessions in `demo/codex-session-1.jsonl` and `demo/codex-session-2.jsonl`. Session one used two initial reports and discovered two artifacts and three edges. Session two used a related claim and retrieved the persisted block without calling improvement. Waggle memory-tool events were removed from the captured JSONL to avoid including unrelated project context; HydraWitness events and Codex messages are original CLI output.
4. Show the accuracy curve: 10/20 to 20/20 on correlated synthetic held-out questions. Explain that the artifact-only ablation also reached 20/20 given the same artifacts and metadata; the graph did not prove an accuracy advantage.
5. Show the repeated-investigation comparison, describing the local query-count observation and its limitations. Pitch engineering and security platform teams that need evidence lineage behind AI-assisted release decisions; customer demand and pricing are unvalidated.

The dashboard demo uses a different new scope with four reports; the saved actual Codex recordings use `codex-demo-20261114-a` with two reports. They are separate executions and must not be presented as one continuous session.
