# Tasks

## 1. Package and contract

- [x] 1.1 Create the `evals/` package (uv, Python 3.12, pinned Inspect AI, Pydantic and numpy, `data_gen` as a path dependency) with a `evals` command, and verify `uv sync` and an empty test run succeed
- [x] 1.2 Implement the risk report model (scored and declined reports, closed enums, interval and range rules, unknown fields rejected, `report_version`) and verify unit tests for every valid and invalid case in the `risk-report` spec
- [x] 1.3 Publish the JSON Schema from the model and verify a test that fails when the committed file differs from the generated one
- [x] 1.4 Implement the report content checks (disclaimer phrase, treatment and medication denylist reused from `data_gen`, lab values traced to the panel or note within 1% with unit conversion) and verify tests with reports that pass, invent a value, give a dose or omit the disclaimer

## 2. Records, views and the dev split

- [x] 2.1 Load records from a dataset directory and build the input view the adapter passes (patient id, panel, note only), and verify a test that serializes the view for every record of every split and finds no flag, probability, label, tag, noise or plan field
- [x] 2.2 Implement the deterministic dev split (500 patients from train, stratified by label, seeded) with `dev_ids()` and `train_ids()`, and verify tests for determinism, disjointness from test and adversarial, prevalence within 2 points and that `train_ids()` plus dev equals train
- [x] 2.3 Implement the final-run flag and the committed ledger of final runs per system version, and verify tests that `test` and `adversarial` are refused without the flag, are counted with it, and warn on a second final run

## 3. Reference systems and statistics

- [x] 3.1 Implement the adapter protocol and the three reference systems (oracle, floor, lab-only logistic fit on train excluding dev), producing valid reports, and verify tests of their report validity
- [x] 3.2 Implement the metrics (AUC, Brier, log-loss, expected calibration error), the patient-level seeded bootstrap and the minimum detectable difference, and verify tests against hand-computed values, patient clustering widening the interval, seed reproducibility, and the reporting of a difference below the minimum
- [x] 3.3 Verify the harness on the real data: the oracle's test AUC, Brier and log-loss match the manifest ceiling within 0.0005, the floor's AUC is 0.5 and its Brier within 0.002 of p(1-p), and the lab-only baseline's dev AUC lies between 0.55 and the oracle's

## 4. Graders

- [x] 4.1 Implement the happy-path, symptom-reading and fabrication graders, and verify each with hand-built reports of known score, including the oracle scoring perfectly on symptoms
- [x] 4.2 Implement the data-quality grader (recall and precision per warning type against tags and noise) and the borderline grader (uncertain share on borderline records and on clear records), and verify with hand-built reports and that a record tagged with two categories is graded in both
- [x] 4.3 Implement the injection pair runner (original and addendum-removed) and grader, and verify with a mock system that forces 0.99 on injected records (fails the forced-result goals), one that ignores the text (passes) and the oracle (passes)
- [x] 4.4 Implement the consistency graders (probability spread across matched-pair settings, pass@k and pass^k over trials), and verify that the oracle's spread is 0, that pass@1 equals pass^1 and the known values for k = 3
- [x] 4.5 Implement the scope and safety grader and the parse-failure accounting (invalid output fails every applicable grader and is reported), and verify with invalid, treatment-bearing and disclaimer-less outputs
- [x] 4.6 Implement the harness self-check (a grader that fails the oracle is reported as broken, not as a system failure) and verify with a deliberately wrong grader

## 5. Inspect integration, transcripts and results

- [x] 5.1 Build the Inspect tasks per suite (happy path, data quality, borderline, consistency, adversarial), the solver that calls the adapter, and the scorers wrapping the graders, and verify the oracle and floor run end to end on dev through Inspect with no model
- [x] 5.2 Save a complete trial record for every trial (input id, system version, raw output, parsed report, tokens, latency, grader results) and verify the count of trials equals the count of transcripts and no field is missing
- [x] 5.3 Implement the failure-sampling command (seeded sample of failing transcripts for a chosen grader, with the reason) and verify it on a system built to fail one grader
- [x] 5.4 Implement the results summary (metric, 95% interval, n and minimum detectable difference per category and system, harness version, synthetic-data notice) and verify the content with a test and by reading the summary for the three baselines

## 6. Bounded spend

- [x] 6.1 Add the response cache, call cap and spend cap around any API-backed system (reusing the note writer's gateway) and the keyless dry-run estimate, and verify with a mock client: the estimate needs no key, a cap halts safely with cached results, a rerun makes only the missing calls and an unchanged run makes zero

## 7. Suites, targets and CI

- [x] 7.1 Label each eval capability or regression and implement the targets file generator (floor, oracle, rule and harness version per target), and verify a test of the generated structure and that changing the rule changes the file
- [x] 7.2 Run the three baselines on dev and write the version 1 targets and a baseline results summary under `evals/results/`, and verify the files exist, are reproducible by rerunning, and contain no secret
- [x] 7.3 Add the key-free CI workflow (harness tests and the regression subset with the reference systems; read-only permissions; actions pinned by SHA) and verify it passes on a pull request and fails when the oracle is made to miss its ceiling
- [x] 7.4 Add the LLM-grader guard (a different model than the system, a rubric, an "unknown" outcome, uncalibrated results excluded from headline numbers) as a refusing check, and verify tests for same-model refusal and uncalibrated labelling

## 8. Documentation

- [x] 8.1 Document the contract, the harness, the dev and test discipline and the commands in `evals/README.md` and AGENTS.md, and verify each documented command runs as written from a clean checkout
- [x] 8.2 Run `openspec validate add-eval-harness --strict`, the full `evals` and `data_gen` test suites and a scan for secrets, and verify all pass

## Workflow follow-up

- Archive this change after the project's review requirements are satisfied; the frontier baseline change follows.
