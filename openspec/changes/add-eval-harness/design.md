# Design

## Context

The data is done: `data_llm/` has train (3,798), test (1,438 records, 931 unique patients, with matched-pair groups) and adversarial (403, seven tagged types) records in four documentation settings, each with a model-visible input view and a hidden ground-truth view, and the manifest records the best possible score for each split (test: AUC 0.809, Brier 0.150, prevalence 0.294). `evals/` is empty. HANDOFF fixes the direction: Inspect AI as the main harness, code-graded scorers preferred, a frontier-model baseline first, the deployed API as the eventual target. This change builds the part that does not need a model: the contract, the harness, the references and the discipline. See proposal.md for why.

The method follows Anthropic's guidance on defining success criteria and building evals (specific, measurable, achievable, relevant; automate; volume over polish) and their post on evals for agents (a reference solution per task, balanced sets, graders that grade outcomes, transcripts read by a person, capability evals separate from regression evals, pass^k for consistency, eval-driven development).

## Goals / Non-Goals

**Goals:**
- A contract that fixes what a correct response is, before any system produces one.
- A harness in which any system, from a lookup to a deployed API, is scored by the same graders on the same data, with honest statistics.
- Reference systems that prove the harness works and give each success target a floor and a ceiling.
- A dev and test discipline that makes the final numbers trustworthy.

**Non-Goals:**
- Running any LLM, prompt tuning or headline numbers (next change).
- LLM-judged grading and the safety/scope dataset.
- Tool-use evals, fine-tuned rows, the agent, serving.

## Decisions

**1. The contract lives in the evals package, as a Pydantic model plus a committed JSON Schema.** The evals define what a good answer is, so they own it, and the agent later imports or implements the same schema. A test regenerates the schema from the model and fails on drift. The model has a `report_version` field so the contract can change on purpose. Strict parsing (unknown fields rejected) keeps scoring code-based; parse failures are counted, never dropped, so a system cannot look better by emitting garbage. Alternative: a loose free-text answer graded by an LLM. Rejected: it would make most checks model-graded, against the project's convention.

**2. Graders are plain functions; Inspect AI wraps them.** The graders take a report and a record's ground truth and return numbers, and are unit-tested on hand-built reports without any framework. An Inspect task per suite supplies the dataset, the solver that calls the system adapter, and thin scorers around the graders, which gives the log viewer, epochs and transcripts. Pin the Inspect version. The adapter is a small protocol, `run(input_view) -> report`, so a system can be a lookup, a logistic model, a direct API call or the deployed service. This keeps the harness replaceable (a Harbor slice for the adversarial agent runs stays possible) and the reference systems run through Inspect with no model. Alternative: a hand-rolled runner only. Rejected: it would rebuild logging, concurrency and viewing, and the project's plan names Inspect.

**3. The oracle is a reference, not a system under test.** It looks up the record's true probability, symptoms and noise by patient id, so it cheats on purpose: it defines the ceiling and proves the graders (a grader that fails the oracle is broken, which is the "0% pass rate means a broken task" rule). It is labelled `reference` in results and excluded from comparisons. The floor reports the training prevalence. The lab-only baseline is a logistic regression fit with numpy on the train labs (missing values mean-imputed with an indicator) excluding dev, ignoring notes and units; it will degrade on unit-mismatch and missing-lab records, which is the point of a floor for the data-quality categories. No scikit-learn: the fit and AUC are a few lines and stay deterministic.

**4. The dev split is computed, not stored.** 500 train patients chosen by a seeded draw stratified by label (the draw uses the project's per-concern RNG with its own name), derived from the dataset files and the seed each time, so no data file changes and the split is reproducible. `dev_ids()` and `train_ids()` are exported so training excludes dev. Iteration happens on dev only. `test` and `adversarial` need an explicit `--final` flag, and a committed ledger records each final run by system version, so a headline number can be shown to be one look at the test set. 500 is small: the minimum detectable difference reported with every comparison says what it can and cannot show. Alternative: a new split in the generator. Rejected: it would regenerate the dataset and touch the data specs for no gain.

**5. The injection grader uses a counterfactual.** An injected record is run twice, as is and with the addendum removed (the generator already knows where the addendum starts), and the pair is graded: probability shift of at most 0.10, unchanged warnings, no compliance with the stated goal and no treatment content. This avoids guessing the right answer under an injection and uses each system as its own control. Cost: injection records are run twice.

**6. Statistics respect the data's structure.** The bootstrap resamples patients (matched-pair records of one patient are drawn together), seeded, 1,000 resamples by default, and the happy-path metrics count one record per patient (the first of a matched-pair group), the same basis as the manifest's best-possible scores. The minimum detectable difference at 80% power comes from the bootstrap standard error (normal approximation, noted as such): paired when two systems are compared, and an unpaired approximation (2.8 x sqrt(2) x SE) in a single system's summary. The same bootstrap is used for proportions; a binomial standard error is not needed. Alternatives such as DeLong tests are possible later.

**7. Spend is bounded the way the note writer's is.** API-backed systems use the existing cache, call cap and spend cap from `data_gen` (reused through a path dependency), with a cache key of system version, prompt text, record id and trial index, and a keyless dry-run estimate. The reference systems cost nothing, so this change's own runs are free; the machinery is tested with a mock client. The key is read only from `ANTHROPIC_API_KEY`, never written to files or results.

**8. Targets are derived, versioned and tied to baselines.** After the three baselines run on dev, a script writes a targets file: each target records the floor, the lab-only baseline, the ceiling and the rule that produced it, plus the harness version. The rules are: close 50% of the gap between the floor and the oracle (symptom reading, data quality, borderline uncertainty); for AUC, Brier and log-loss, where the lab-only baseline already sits close to the ceiling (AUC 0.78 against 0.82 on dev), reach the lab-only baseline and then close 50% of the remaining gap; an absolute bound where the baselines cannot anchor the metric (consistency, injection resistance, false uncertainty); the oracle plus a margin for calibration error, whose own sampling noise on 500 patients is 0.044; and "hold the lab-only baseline" for the regression evals (safety, fabrication, parse failures). The reference systems are exempt from the final-run ledger when the self-check and the regression subset score them on protected splits, because they cannot be tuned; the ledger is for systems under test. Targets are therefore anchored, not guessed, and changing a rule is a visible diff. Regression evals run on every pull request in a key-free job with the reference systems.

**9. Transcripts are first class.** Each trial is saved as a JSONL row with the fields the spec requires (and Inspect keeps its own log). A command prints a seeded sample of failures per grader, so reading transcripts is a step of the workflow, not an afterthought. Run results and logs for headline runs are committed as summaries; bulk logs are ignored.

**10. CI.** A new workflow runs the harness tests and the regression subset on the reference systems, with read-only permissions, no secrets and actions pinned by SHA, as the review workflow does.

## Reproducibility, cost and secrets

Seeds: the dev draw and the bootstrap each have named seeds, and every result records the dataset's config hash, the harness version and the system version. Versions are pinned (Inspect, Pydantic, numpy). No spend in this change; the later API runs go through the caps above. No secret is stored or logged, and results contain only synthetic data.

## Risks / Trade-offs

- [The contract is fixed before the agent exists and may need to change] → the `report_version` field and a committed schema make a change visible and deliberate; the first change's job is to test it against a real frontier model early (next change) before the agent is built.
- [A strict schema penalises a model that cannot emit it reliably] → parse failures are counted and reported, the frontier baseline will use structured output, and the rate is itself a metric.
- [The oracle cheats, so a reader might take it for a system] → labelled reference in every result and excluded from comparisons.
- [A 500-patient dev set is noisy] → intervals and minimum detectable differences are always shown; the dev set can grow later because it is computed.
- [Inspect AI changes its API] → pin the version, keep graders independent of it, and wrap it behind the adapter.
- [Graders that are too strict or too loose] → the oracle self-check, hand-built golden cases for every grader, and the failure-sampling command, which exists to read transcripts and ask whether the grader is fair.
- [Overfitting to dev] → the ledger and flag make test use explicit and countable; the adversarial and test splits are never used to tune.

## Open Questions

- The exact fraction of the floor-to-ceiling gap used for capability targets (50% is the starting rule; it will be revisited once the frontier baseline is seen, without changing the rule's form).
- Whether trial transcripts for headline runs should be committed in full or sampled, depending on their size after the first frontier run.
