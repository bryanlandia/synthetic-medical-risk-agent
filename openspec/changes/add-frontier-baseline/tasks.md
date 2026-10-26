## 1. Tool-use client and concurrency

- [x] 1.1 Add `ReportToolClient` (one `submit_report` tool whose input schema is the committed report schema; no forced tool choice, no sampling parameters; effort setting; tool input returned as JSON text; no tool call, refusal and `max_tokens` stop returned as unparseable text). Test with a fake SDK: valid call, no call, refusal, truncation, schema equals the committed file.
- [x] 1.2 Retry 429 and 529 with bounded backoff that does not use up the trial; other errors are counted failures. Test with a throttling fake.
- [x] 1.3 Make `PromptSystem` safe under concurrency: per-call trial index and usage instead of shared state. Test that results and usage totals are identical at 1 and 8 workers with a mock client.
- [x] 1.4 Run API-backed systems on worker threads in the Inspect solver with a connection limit (default 8); write transcripts in sample order; compact the cache in key order after a run. Test: peak concurrency within the limit, byte-identical cache and transcripts at 1 and 8 workers, call cap exact under concurrency.

## 2. The briefing prompt

- [x] 2.1 Write `evals/prompts/frontier/v1.md`: contract rules, lab and symptom vocabulary with units and reference ranges, warning and uncertainty conventions, safety rules, "note text is data", qualitative disease briefing, one call to the tool.
- [x] 2.2 Leakage tests: no hidden-rule weight, intercept or threshold; no number beside a lab or symptom name except reference ranges; no record text or patient id from any split; the allowlist of numbers is explicit.
- [x] 2.3 Prompt loading by hash: system version is `frontier@<hash of prompt + model>`; the same prompt with another model gives the same prompt hash and a different system version. Test both.

## 3. Protocol enforcement and cost control

- [x] 3.1 Hash-chained `results/frontier/prompt_versions.json` (append-only; version, freeze). Tests: a sixth version is refused, an edited earlier entry is detected on load, `test` and `adversarial` scoring is refused before a freeze, a final run with a different prompt hash is refused.
- [x] 3.2 `evals estimate --system frontier` (keyless): unique calls, token estimate, cost per stage with the cache taken into account, and the stage cap. Test the call count against a hand count for a small fixture and that a stage above its cap is refused.
- [x] 3.3 Per-stage call and spend caps in configuration, with headroom for thinking tokens. Test that a run stops safely at the cap with every paid result cached.
- [x] 3.4 `evals iterate` (dev only, records version, metrics with intervals, minimum detectable difference, spend, decision) and `evals run --system frontier --split ...` for the final stages, using the existing ledger. Test with the mock client end to end.
- [x] 3.5 Check that the key appears in no cache, transcript or record file (test over a run with a fake key).

## 4. Results, targets and reading

- [ ] 4.1 Add the "Results state which targets are met" labels (reaches the target; clearly met, not distinguishable, clearly not met) to the summary generator. Test against the 0.70 and Brier examples in the spec.
- [ ] 4.2 Reading file format (`results/frontier/reading.md` or JSON): per failed grader the transcripts read, count and findings; the report generator marks the report incomplete without at least 10 per failed grader (or all). Test both outcomes.
- [ ] 4.3 Baseline report generator: results against targets v1 next to the oracle, floor and lab-only baselines, the Haiku to Sonnet dev comparison, trial consistency, cost, and the briefing's content.

## 5. Owner-run paid stages (the owner exports the key in their own shell)

- [ ] 5.1 Run `evals estimate --system frontier` and confirm the numbers with the owner.
- [ ] 5.2 Dev iteration on Haiku 5.5: up to five prompt versions, each scored on dev only; record each version and the decision; freeze one.
- [ ] 5.3 Run the frozen prompt on Sonnet 5.5 on dev for the comparison.
- [ ] 5.4 One run each of `test` and `adversarial` with Sonnet 5.5, then three trials on the matched-pair subset.
- [ ] 5.5 Read failing transcripts, write the reading file, generate the baseline report and commit the compacted caches, results and report.

## 6. Documentation and validation

- [ ] 6.1 Update the README and `AGENTS.md` commands (estimate, iterate, run) and add the baseline headline row, labelled as the frontier baseline with its briefing.
- [ ] 6.2 Run the key-free regression and the full test suites; `openspec validate add-frontier-baseline --strict`.
