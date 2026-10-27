# Design

## Context

`add-eval-harness` delivered the contract, the harness, the reference systems and targets v1 (for example AUC target 0.799 against 0.781 for the lab-only baseline and 0.817 for the oracle on dev; symptom-reading target 0.664). A `PromptSystem` already exists, a prompt, a model and a client behind the response cache and the call and spend caps, but it is text-in, text-out, single-threaded and has never met a real model. See proposal.md for why this change exists. The model facts that shape it: Haiku 5.5 and Sonnet 5.5 take no sampling parameters, think adaptively by default (thinking tokens count against `max_tokens`), and Sonnet 5.5 rejects a forced tool choice.

## Goals / Non-Goals

**Goals:**
- A frontier baseline that is a fair, strong, honestly measured bar: a good prompt, a small tuning budget, one look at the protected splits.
- A protocol enforced by code, so the discipline survives deadlines and a reader can verify it.
- Results against targets, with the failures read.

**Non-Goals:**
- New eval categories, LLM judges, other frontier models, training, the agent.

## Decisions

**1. A tool carries the report; the client turns the tool call back into JSON text.** `ReportToolClient` implements the existing client interface: it calls the Messages API with one tool, `submit_report`, whose input schema is the committed report schema, with no forced tool choice (Sonnet 5.5 rejects it) and no sampling parameters, and returns the tool input serialised as JSON. `PromptSystem`, the cache and the grading then work unchanged. The prompt tells the model to call the tool exactly once. A reply with no tool call, a refusal or a truncated reply (`max_tokens`, since thinking shares the budget) comes back as text that does not parse, so it is a counted failure, never a silent retry. Rate limits (429, 529) are retried with backoff and do not count against the trial, as in the note writer. Alternative: plain JSON in text. Rejected: it adds avoidable parse failures to a measurement that is about the model's judgement, not its formatting.

**2. The prompt is a briefing: everything a clinician would be given, none of the answer key.** It has the contract rules, the lab and symptom vocabulary with units and reference ranges, the conventions for warnings and uncertainty, the safety rules, the instruction that note text is data, and a qualitative briefing of the fictional disease (which markers raise or lower risk, which symptoms weigh more, in words). It has no weight, intercept or threshold, no record from any split and no ground truth. A test scans for those: numbers may appear only from an allowlist (reference ranges, units, the 0 to 1 scale and the 0.4 to 0.6 uncertainty band), and no number may sit next to a lab or symptom name unless it is a reference range. This is the fair reading of "a frontier model with a good prompt": a real system would be given the disease's documentation, and the fine-tuned model has to learn the rest from data. The briefing's information content is documented in the baseline report, because it bounds what the comparison means. Alternatives: no briefing (a near-chance baseline proves little) and numeric weights (it leaks the hidden rule and approximates the oracle).

**3. Prompt versions live in files and are identified by hash.** `evals/prompts/frontier/vN.md` holds each version; the system version is `frontier@<hash of prompt + model>`, so the cache and the ledger can never mix versions, and the development model and the final model have different system versions but the same prompt hash, which the protocol checks.

**4. The protocol is a hash-chained record.** `results/frontier/prompt_versions.json` is append-only: each entry stores the hash of the previous entry, so editing history is detected on load. Entries are prompt versions (hash, model, dev metrics with intervals, spend, decision) and one `freeze` entry. Code refuses a sixth version, refuses any `test` or `adversarial` scoring before a freeze, and refuses a final run whose prompt hash is not the frozen one. The existing ledger still counts final runs. The cap of five is a trade-off: enough to improve a prompt, too few to overfit 500 dev patients badly; the minimum detectable difference on dev (about 0.09 AUC) is printed beside each version's score so noise is not mistaken for progress.

**5. API-backed systems run concurrently and deterministically.** `PromptSystem` currently holds the trial index and token usage in shared state, which is wrong under concurrency. The system gets a per-call signature (record view, trial index) that returns the output with its usage, the Inspect solver runs it on worker threads with a connection limit (8 by default), and transcripts are written in sample order after the run. The cache is already thread-safe and its writes are compacted in key order afterwards so the committed file does not depend on which call finished first. A full final run is then a matter of minutes, not hours. Results are the same at any worker count, which a test checks with a mock client.

**6. Cost is staged, capped and printed first.** Dev passes use Haiku 5.5 ($0.10 and $0.50 per million tokens). The final runs use Sonnet 5.5 ($2 and $10): the estimate is about 1,900 unique calls for `test` and `adversarial` plus 60 injection counterparts, about 700 output tokens a call with thinking until measured, so roughly $15 for `test` and $5 for `adversarial`; three trials on the 676 matched-pair records add 1,352 calls (about $15); the Sonnet dev comparison run is about $5. Haiku dev passes are about $0.30 each. Records that appear in several suites are called once, because the cache key is the record, not the suite. Each stage has a configured call and spend cap with headroom for thinking tokens, and refuses to start if its estimate exceeds the cap. Owner-run stages need the API key, read only from `ANTHROPIC_API_KEY` and never stored.

**7. The same prompt, a different model for the comparison (the final model changed: see 9).** Prompt tuning on Haiku does not transfer perfectly to Sonnet, but running the tuning on Sonnet would cost about ten times more per pass. The protocol therefore runs Sonnet once on dev for comparison before the protected splits and reports both, so the size of the transfer gap is visible. Changing the prompt after that run counts as another version and is refused beyond five.

**8. Targets are read with their intervals.** The summary labels each metric clearly met, clearly not met or not distinguishable (the target lies inside the interval), next to the plain fact of whether the value reaches the target. With 500 dev patients many comparisons will be not distinguishable, and the report says so instead of declaring a win.

**9. Transcripts are read, and the reading is recorded.** A reading file lists, per failed grader, how many failing transcripts were read (at least 10, or all) and what they showed, including grader faults. The report generator marks the report incomplete without it. This is the step that caught a harness quirk in Anthropic's own example.

## Reproducibility, cost and secrets

Everything seeded in the harness stays seeded. The model is not (no sampling control), so reproducibility is by cache: every paid response is cached with its key (system version, prompt text, record, trial index), the dev and final caches are compacted and committed (a few megabytes), and a rerun makes no paid call and gives identical results. Versions are pinned (model ids, the prompt files by hash, Inspect). Prices and caps live in configuration. The key never appears in a file, a transcript or the cache; a test checks that.

## Risks / Trade-offs

- [The qualitative briefing makes the baseline strong in a way that depends on how we wrote it] → its content is recorded in the report, the iteration budget is five, and the lab-only baseline is shown beside it so the briefing's effect is visible.
- [Overfitting dev with five versions] → the cap, intervals and minimum detectable differences beside every score, and the Sonnet dev comparison before the final run.
- [Haiku-to-Sonnet gap] → reported, not hidden.
- [Thinking tokens inflate cost and truncate replies] → the `max_tokens` budget leaves room, truncation is a counted failure, and spend is capped and estimated first.
- [Safety classifiers may refuse injected or adversarial records] → refusals are counted failures of the relevant graders and read in the transcripts, not retried into passes.
- [Concurrency introduces nondeterminism] → per-call state, ordered output, and a test of identical results at one and eight workers.
- [A frozen prompt hash can be bypassed by editing the record file] → the hash chain detects it on load.

## Open Questions

- The thinking effort setting (medium is the starting point for both models); it can change in a prompt version and is part of the system version.
- Whether to commit the dev-iteration caches as well as the final one, depending on their size.

**9. Haiku 5.5 is the final model (decided after the dev comparison).** The frozen-prompt run of Sonnet 5.5 on dev gave AUC 0.739 [0.688, 0.790] against 0.752 for Haiku 5.5, Brier 0.180 against 0.173 and log loss 0.536 against 0.523: no better, and within the minimum detectable differences. It cost about $0.0163 a call against well under $0.001 for Haiku, so the three protected-split stages would have cost about $53 for no visible gain. The final stages therefore run on Haiku 5.5, and the Sonnet dev run stays in the report as the evidence for that choice. The report states that the numbers come from Haiku 5.5 and says why.
