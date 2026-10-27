# Design

## Context

See proposal.md for why. The facts that shape the approach, all observed in the repository:

- `data_gen/data_llm/` holds 4,000 train, 1,000 test and the adversarial records, with LLM-written notes in four documentation settings (shorthand, EHR template, AI scribe, copy-forward). `evals.devsplit.train_ids` gives the train records without the 500 dev ids; `dev` is the only split a model may be chosen on.
- The panel is always written in the usual units. A unit mismatch lives in the note (a lab stated in its alternate unit); a contradiction is a note value that disagrees with the panel (for example a copied-forward stale value); an impossible value is in the panel (decimal shift or negative); a missing value is a null in the panel.
- The hidden rule is logistic in the labs and the true symptom flags, and the note states the flags with hedging, negation and deliberate disagreement. On dev the oracle reaches AUC 0.817, the lab-only baseline 0.781, target v1 is 0.799, and the frontier baseline reached 0.735 on `test`. The true probabilities on dev run from 0.03 to 0.85 at the 5th and 95th percentiles.
- The `data_gen` symptom extractor is an LLM pass and cannot run at serving time. `training/` is empty. The project context fixes CPU serving of the classifier and keeps the LoRA model offline.
- The harness runs any object with `run(view) -> report`, scores it on the same graders, records `--final` runs in the ledger, and already has patient-clustered bootstrap intervals.

## Goals / Non-Goals

**Goals:**
- A small, auditable model that reads labs and note, runs in numpy on CPU, and returns a complete valid report on every record.
- A leakage-proof training protocol: train split without dev only, selection on dev, one look at `test` and `adversarial`.
- A paired comparison with the frontier baseline on the same patients.
- Reproducibility: same data, config and seed give byte-identical model files.

**Non-Goals:**
- The LoRA model, the agent, the API and deployment.
- A gradient-boosted or neural model in the served path. A gradient-boosted model is trained as a diagnostic comparison only, because serving it would need a pickle-style format or a new dependency, and the point of this model is that it is inspectable.
- Matching the hidden rule's exact weights: the classifier learns weights from data; they are not copied from `data_gen/rule.py`.

## Decisions

**1. One new Python project, `training/`, with a numpy-only inference path.** Training uses scikit-learn and MLflow (pinned). The model is exported as JSON with the arrays inline (an `.npz` file embeds timestamps, which would break byte-identical exports), and inference re-implements the tokenizer, the binary feature lookup and the dot products in numpy, with a test that it matches scikit-learn's output to 1e-9 on 200 records. The agent and the evals import the predictor without scikit-learn or MLflow. Alternative: pickle the scikit-learn objects; rejected because pickles execute code on load, break across versions and hide what the model is.

**2. The note reader works on mentions, not on the whole note.** The note is split into lines and sentences; a lexicon of symptom terms (built from the generator's vocabulary and the train notes, and kept in the repository as data) finds mentions of each symptom; a logistic regression on binary features of the mention's clause (its words and word pairs, the previous clause's words, and its words tied to the symptom) classifies it as present, possible or absent. A symptom with no mention is `not_mentioned`; a symptom whose mentions conflict (present in one place and absent in another) is reported as a conflict, and its reading follows a rule chosen on dev (last mention, or the more specific one). The grader scores what the note states; the generator's `note_flag_disagreement` cases are notes that disagree with the hidden flag, which no system can see from the record, so the conflict warning is reported with its recall and no target (the frontier baseline got 0.0 on it). Labels for training come from the plan symptoms of each train record (stated present, hedged, negated; a flag absent from the plan is `not_mentioned`). Why mentions: a whole-note bag of words cannot tell which symptom a negation belongs to ("denies shaking, feels dizzy"). Alternatives: a whole-note classifier per symptom (kept as the comparison on dev; chosen only if it is better and not worse held out), regular expressions only (brittle across four writers), a small transformer (heavier than the task needs and not numpy-servable).

**3. Stated lab values are read by pattern from the note's result lines.** The reader extracts `name (ABBR): value unit` forms and the inline list forms the settings use ("Velorin index 104 mg/dL, Tarnic acid 220 umol/L"), and keeps a value only if the lab name and a number are both unambiguous. Values it cannot read are left out. A stated value in the alternate unit that equals the panel after conversion is a `unit_mismatch`; one that disagrees by more than 1% is a `contradiction`.

**4. The classifier is a regularised logistic regression on labs and symptom readings.** Features: the eight lab values as z-scores from the train mean and standard deviation (train without dev), eight missing indicators (a missing or impossible value is zero-filled at the mean with its indicator on), and the five symptom readings as one-hot present and possible levels (absent and not mentioned are the reference). The L2 strength and the other logistic settings are chosen on dev by log loss from a grid declared before the first run (at most 12 candidates, recorded in MLflow with the choice). The served model is always this logistic regression. A gradient-boosted model is trained on the same features and scored on dev only as a diagnostic, and its result is reported next to the logistic one; if it were much better, that would be a finding about the logistic family and a reason for a later change, not a reason to serve a model with no numpy export. The rule being logistic means this family is well specified, so the expected result is a model close to the oracle ceiling; the model card says that this reflects the synthetic rule, not what a real disease would allow. Alternative: put the note embedding in as features; rejected for this change because it adds style information the label does not depend on (the held-out-setting experiment is the check on this).

**5. Calibration is cross-fitted on train without dev.** Out-of-fold predictions from five folds (stratified, seeded) fit a Platt scaling; if it does not improve log loss on the out-of-fold predictions it is dropped. Isotonic regression is not used: with about 3,500 records it overfits the middle of the range, where the borderline band is. The probabilities are never clipped, and the spec's spread check (5th percentile at most 0.10, 95th at least 0.60) catches a model that has collapsed to the mean as the frontier baseline's probabilities partly did.

**6. The report is assembled by code, around the model.** `uncertain` is the band rule on the probability (the frontier baseline's largest borderline failure was a flag decoupled from the probability). `labs_used` is the panel's non-null, plausible values. Warnings come from the checks in decision 3 and from range checks against the generator's plausible ranges (`data_gen.labs`). Evidence strings come from fixed templates filled with the record's own values, ordered by each feature's contribution to the logit (exact for a logistic model), two to five of them, each under 300 characters. There is no free text from a model, so there is nothing to fabricate or to make unsafe; tests still run the safety and fabrication graders on every final run, and the evidence templates are checked against the project's medication denylist.

**7. Tracking and artifacts.** Each training run logs to a local MLflow file store (`training/mlruns/`, not committed) the parameters, seed, data hash (the manifest's config hash), the train ids' hash, dev metrics with intervals, the held-out table and the model files. The chosen model's files, `training/model/` (one JSON file per component, with the lexicon inside the reader), a metrics summary and the model card are committed, with the model hash and the MLflow run id written in the card. The test suite fails if the card's hash and the files disagree. Training with a protected record is refused at the loader, by id, before any fitting.

**8. The evals gain a `classifier` system and a comparison command.** `uv run evals run --system classifier --split dev|test|adversarial` loads the committed model; the system's version is the model hash. `test` and `adversarial` need `--final` and a model hash recorded as frozen on dev (the same one-look rule as the frontier baseline, through the existing ledger). `uv run evals compare --a classifier --b frontier` reads both runs' transcripts, pairs them by patient, and writes `results/classifier/comparison.md` with the values, the paired differences and their patient-clustered bootstrap intervals, and the verdict wording the frontier report uses. The classifier is not a reference system: it is a system under test and appears in comparisons.

**9. Held-out-setting experiment.** The reader is trained four times on three settings of the train split (without dev) and scored on the fourth setting's train records plus dev records of that setting; the table also gives the in-distribution accuracy. The setting of a record comes from the record's style field, which the reader never sees as a feature. Any held-out accuracy below 0.90 is written into the model card with the failing phrases, not tuned away silently.

**10. Determinism and cost.** Every random draw uses a seed from one config; the tokenizer is deterministic; the exporter writes sorted keys and full-precision float64 so two runs give the same bytes (a test). There is no API call and no spend. The expected training time is minutes on a laptop CPU.

## Risks / Trade-offs

- [Dev is used to choose the model, so dev numbers are slightly optimistic] → the candidate grid is declared first and small, the numbers that count are the one-look `test` and `adversarial` runs, and the report says so.
- [The reader may learn one writer's phrasing] → the leave-one-setting-out experiment, the 0.90 floor, and the held-out table in the model card.
- [A logistic model on a logistic rule will look excellent] → the model card and the comparison report state that this is a synthetic rule, and that the oracle ceiling (AUC 0.817 on dev) bounds what any system can show.
- [Copy-forward notes carry stale lab values] → the reader keeps stated values separate from the panel; the classifier reads the panel only, and a stale note value becomes a `contradiction` warning, not a feature.
- [A note that mentions a symptom with an unfamiliar word is read as not mentioned] → measured by symptom-reading accuracy on dev and by the held-out table; the lexicon is data, so a gap is fixed by adding terms and retraining, and every addition is checked against dev only.
- [The borderline target (uncertain rate of at least 0.5 on true-borderline records) may stay out of reach] → a classifier cannot flag a record as borderline unless its own estimate falls in the band; the result is reported against the target with its interval, not engineered by widening the band.
- [Packaging an MLflow dependency for a small model is heavy] → it is a training-only dependency; the predictor imports numpy only.

## Migration Plan

New directories and a new system in `evals/`; nothing existing changes behavior. Rollback is removing `training/` and the `classifier` system.
