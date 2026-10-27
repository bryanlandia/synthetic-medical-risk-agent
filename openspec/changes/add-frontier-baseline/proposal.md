# Proposal

## Why

The harness and its reference systems exist, and targets v1 are derived from them, but no real model has been scored. The project's headline claim compares a fine-tuned small model with a frontier model given a good prompt, and the frontier model is the baseline to beat. It has to be measured the way the harness demands: a prompt tuned on dev only, a small and honest tuning budget, one look at the protected splits, results against the targets, and the failures read by a person before any number is quoted.

## What Changes

- Add the **frontier baseline system**: a prompted model that returns the risk report through a tool whose input schema is the report contract. Haiku 5.5 is used while the prompt is developed on dev and, after a dev comparison showed Sonnet 5.5 no better, for the final numbers. The prompt carries the contract, the lab and symptom vocabulary, the data-quality and uncertainty conventions, the safety rules, and a **qualitative disease briefing** (which markers raise or lower risk and which symptoms weigh most, in words only; no weights, thresholds or intercept).
- Add a **prompt iteration protocol**: at most five prompt versions, each scored on dev only and recorded (hash, metrics, decision); the last version used is frozen, and the final run refuses any other prompt.
- Add the **final run protocol**: one run on `test` and one on `adversarial` with Haiku 5.5 (each recorded in the ledger), a dev run of Sonnet 5.5 for comparison, and three trials on a matched-pair subset for pass^3.
- Make API-backed systems **run concurrently and deterministically** (per-call trial index and usage, no shared state), so a full run takes minutes and gives the same results at any worker count.
- Report the results **against targets v1**, stating for each metric whether the value reaches the target and whether that is clearly met, clearly not met, or not distinguishable from the target, and record the transcripts a person read, with what they showed.
- Add the `evals estimate` command and spend caps for each stage.

## Capabilities

### New Capabilities
- `frontier-baseline`: the baseline system and its prompt, the iteration and final-run protocols, spend bounds per stage, and what the baseline's results report must contain.

### Modified Capabilities
- `eval-harness`: two added requirements. Results state which targets are met (with interval-aware wording), and API-backed systems give the same results at any concurrency.

## Out of scope

- The safety and scope dataset, LLM-judged grading, and any new eval category (tool-use evals wait for the agent).
- Fine-tuning, serving, the agent and deployment.
- Giving the baseline the hidden rule's numbers, or any use of `test` or `adversarial` while iterating.
- Comparing several frontier models: one final model is scored.

## Eval categories affected

All of them get their first real-model row: happy path, symptom reading, data quality, borderline, consistency, adversarial and the fabrication and safety checks.

## Impact

- Extends `evals/` only (a tool-use client, the baseline prompt, a protocol recorder, concurrency, a few CLI commands); no change to `data_gen/` or the data.
- Spend: roughly $0.50 to $1 for each Haiku dev pass (about $1.50 for five), then about $8 for the Sonnet dev comparison (measured), and about $3 for the Haiku runs on `test`, `adversarial` and the three trials; caps are set per stage. The runs are done by the owner, since they need the API key.
- Results, prompt versions and the final prompt are committed; the key never is.
