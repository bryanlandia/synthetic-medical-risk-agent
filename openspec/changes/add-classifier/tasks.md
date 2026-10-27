## 1. Project and data access

- [x] 1.1 Create the `training/` uv project (Python 3.12, pinned numpy, scikit-learn and MLflow; `data_gen` as a path dependency) with a `training` package, a CLI entry point and a README stating the synthetic-data notice.
- [x] 1.2 Add the record loader: reads `data_gen/data_llm/` train records, drops the dev ids with `evals.devsplit.train_ids`, and raises an error naming the record if given a `test`, `adversarial` or dev record. Test all three refusals and that the loader returns exactly the train-without-dev ids.
- [x] 1.3 Add the feature builder over the input view only, rejecting any ground-truth key (reuse the harness's clean-view check). Test the rejection, zero-fill with missing indicator for null and impossible values, and conversion of an alternate panel unit.

## 2. Note reader

- [x] 2.1 Build the symptom lexicon as repository data from the generator's vocabulary and the train notes, with a script that regenerates it; test that every term is lowercase, deduplicated and maps to one of the five symptoms.
- [x] 2.2 Implement mention finding and the mention-context classifier (the clause's words and word pairs, the previous clause's words, logistic regression), with training labels from the plan symptoms of train-without-dev records. Test on hand-written notes covering negation, hedging, two symptoms in one sentence and no mention.
- [x] 2.3 Implement the stated-lab-value reader for the result-line and inline-list forms. Test on each documentation setting's forms, on an alternate-unit value and on a note with no values.
- [x] 2.4 Implement the conflicting-mention rule and pick its variant (last mention or the more specific one) on dev. Test both variants and that the choice is recorded.
- [x] 2.5 Export the reader (one JSON file with the arrays inline, sorted keys, full-precision floats) and a numpy-only inference path. Test that it matches the scikit-learn output to 1e-9 on 200 records and that it runs with the network disabled and no API key.
- [x] 2.6 Score the reader on dev with the symptom-reading grader and write the accuracy with its interval. Eval: at least 0.95, otherwise record the miss and read 20 failing notes.
- [x] 2.7 Run the leave-one-setting-out experiment and write the held-out table. Eval: any setting below 0.90 is listed with its failing phrases in the model card.
- [x] 2.8 Score the reader on dev notes with each catalog injection addendum appended, against the same notes without it (the real injection records are in the protected adversarial split, which only a `--final` run reads). Eval: readings identical for at least 95% of pairs, differences listed.

## 3. Classifier

- [x] 3.1 Implement the logistic model (the served one) and the gradient-boosted diagnostic on the same feature set, with the logistic candidate grid (at most 12) declared in a config file before any dev scoring. Test that the grid is read from the file and that a larger grid is refused.
- [x] 3.2 Implement cross-fitted Platt calibration on train without dev, dropped when it does not improve out-of-fold log loss. Test on a synthetic miscalibrated model and on an already calibrated one.
- [x] 3.3 Wire MLflow tracking: parameters, seed, data hash, train-ids hash, dev metrics with intervals, held-out table, model files. Test with a temporary file store that the run holds each of them.
- [x] 3.4 Export the chosen model and test that two training runs with the same seed give the same file hashes, and that a different seed changes them.
- [x] 3.5 Choose the logistic settings on dev by log loss and record the choice; report AUC, Brier, log loss and ECE with intervals against targets v1, and report the gradient-boosted diagnostic next to them without serving it. Eval: ECE at most 0.0643 and the 5th and 95th probability percentiles at most 0.10 and at least 0.60.

## 4. Report and system

- [x] 4.1 Implement report assembly: the `uncertain` band rule, `labs_used`, symptoms from the reader, and contribution-ordered evidence templates (2 to 5 items, each under 300 characters). Test every report validates against the schema, `uncertain` matches the band on 1,000 records, and the evidence passes the medication denylist.
- [x] 4.2 Implement the data-quality checks (missing, unit mismatch from the note's stated unit, impossible from the plausible ranges, contradiction beyond 1% after conversion, conflicting mentions). Test each type, that a clean record gives an empty list, and that no warning appears for an absent problem.
- [x] 4.3 Add the `classifier` system to `evals` (version is the model hash, not a reference system) and register it in the CLI. Test through the harness with the mock dataset that it returns valid reports and that three trials are identical.
- [x] 4.4 Run `uv run evals run --system classifier --split dev` and the fast regression; read 20 failing happy-path and 20 failing borderline transcripts and write what they show. Eval: fabrication 0, safety 1, parse failures 0 on dev.
- [x] 4.5 Measure latency and size: median and 95th percentile time per report over the 500 dev records in one thread, and the model file sizes. Eval: 95th percentile under 100 ms and under 10 MB in total.

## 5. Final runs and comparison

- [x] 5.1 Freeze the model hash on dev and add the one-look rule for the `classifier` system to the ledger (a second final run for the same hash is refused unless forced). Test the refusal and the recorded forced run.
- [x] 5.2 Run `test` and `adversarial` with `--final`, and the three-trial consistency run on the matched-pair subset. Eval: the three trials of every matched-pair record give identical reports, and the consistency mean SD (spread across the four documentation settings of one patient) is at most 0.05 with at least 90% of pairs passing, as the targets say.
- [x] 5.3 Add `uv run evals compare --a classifier --b frontier`: pairs the two systems' transcripts by patient and writes the values, paired differences with patient-clustered bootstrap intervals and verdicts for AUC, Brier and log loss to `results/classifier/comparison.md`. Test on two mock systems with a known difference and on identical systems (difference zero, not distinguishable).
- [x] 5.4 Read failing transcripts for each target the classifier misses, record them in a reading file as the frontier baseline did, and generate the comparison report. Eval: the report is complete (no missing readings).

## 6. Documentation and validation

- [x] 6.1 Write the model card (intended use, data, train and dev split, held-out table, weaknesses, the note that the synthetic rule is logistic, the model hash and MLflow run id) and a test that fails if its hash disagrees with the committed model files.
- [x] 6.2 Update `AGENTS.md` and the READMEs with the training and classifier commands, and add the classifier row to the evals README headline table next to the frontier baseline.
- [x] 6.3 Run the full test suites for `training/` and `evals/`, the fast regression and `openspec validate add-classifier --strict`.
