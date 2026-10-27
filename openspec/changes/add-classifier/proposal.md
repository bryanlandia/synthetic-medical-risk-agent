# Proposal

## Why

The frontier baseline is scored: Haiku 5.5 with a qualitative briefing reaches AUC 0.735 on `test` (target 0.799, the lab-only baseline 0.781 and the oracle 0.817 on dev), and its probabilities are compressed and its `uncertain` flag is not tied to its probability. The project's headline claim is that a small model trained on this data beats a prompted frontier model on the same evals, and runs cheaply on CPU. No trained model exists yet (`training/` is empty). This change builds the classifier that will be served live, trains it only on the train split without dev, and scores it through the same harness, so the first real comparison with the frontier baseline can be made.

## What Changes

- Add a **note reader** that turns a note into the five symptom readings (present, possible, absent, not mentioned) and into the lab values the note itself states, on CPU with no API call. It is trained on the symptom plan labels of the train split (excluding dev), seeded and small, and is scored by the same symptom-reading grader as every other system.
- Add the **risk classifier**: a calibrated probability from the lab panel (normalised to the usual units, with missing-value indicators) and the note reader's symptom readings. A logistic model is the main candidate and a small gradient-boosted model is the comparison; one is chosen on dev by log loss, and the choice is recorded. Calibration is fit on train without dev.
- Add **deterministic report assembly** around the model: the `uncertain` flag is derived from the probability (the 0.4 to 0.6 band), `labs_used` and `symptoms` come from the record, data-quality warnings come from checks on the panel and the note's stated values (missing, unit mismatch, impossible value, contradiction, symptom statements that disagree), and evidence strings cite the record's own values. No model writes text.
- Add **MLflow tracking** for every training run (parameters, seed, data hash, metrics, model file) and a **model card** file that states the intended use, the synthetic data, the training and dev splits and the held-out results.
- Add the **`classifier` system** to the evals (`uv run evals run --system classifier`), scored on dev while iterating, then once on `test` and once on `adversarial` with `--final`, plus three trials on the matched-pair subset (deterministic, so the three trials must agree exactly).
- Add a **held-out-setting experiment**: train the note reader on three of the four documentation settings and score it on the fourth, to show whether it learned the clinical content or the style of one writer.
- Report the **comparison with the frontier baseline** per metric with intervals and a paired difference on the same patients, using the minimum detectable differences already in the summaries.

## Capabilities

### New Capabilities
- `note-reader`: reading symptom statuses and stated lab values from a note on CPU, how it is trained and how it is held to account (symptom-reading accuracy, held-out setting, injection text ignored).
- `risk-classifier`: the probability model, its inputs, training protocol and leakage rules, calibration, tracking, model card, the report it returns, determinism and CPU serving limits.

### Modified Capabilities
- None. The harness already runs any system that returns a report; the eval-harness requirements do not change.

## Out of scope

- The LoRA fine-tuned language model (a later change, offline comparison only, needs a GPU).
- The agent, the API and the web app, and wiring the classifier in as an agent tool (the classifier is delivered as a Python package and a model file the agent change will load).
- New eval categories, and tool-use evals.
- Anything that reads `test` or `adversarial` while building or choosing the model, and any feature taken from the ground-truth view of a record.
- Training on a different dataset: the data in `data_gen/data_llm/` is used as it is.

## Eval categories affected

All of them get a classifier row: happy path, symptom reading, data quality, borderline, consistency, adversarial and the fabrication, safety and parse checks. The prompt-injection category is expected to pass by construction, since no model reads the note as an instruction; this is checked, not assumed.

## Impact

- New `training/` package (Python 3.12, uv, pinned): note reader, features, classifier, calibration, MLflow runs, model card and a small CLI; the trained artifacts are small enough to commit.
- `evals/` gains a `classifier` system and its comparison report; no change to the report contract or the graders.
- Spend: none. Training and scoring run on a laptop CPU and call no API; the only paid results are the existing frontier baseline numbers, which are read from their committed files.
- Reproducibility: every random draw is seeded; the data hash and the dev ids are recorded in each run; the model files are checked into the repository with their hashes.
