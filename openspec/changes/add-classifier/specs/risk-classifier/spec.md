# Spec Delta

## Purpose

Defines the trained risk classifier that is served on CPU: what it reads, how it is trained without touching protected data, how it reports, and how it is compared with the frontier baseline on the same patients.

## ADDED Requirements

### Requirement: The classifier reads only the input view
The classifier SHALL compute its features from the lab panel (values and units) and the note, through the note reader, and from nothing else. It MUST NOT read ground-truth fields, plan fields, the dataset split, or the patient id as a feature.

#### Scenario: A ground-truth field is rejected
- **WHEN** the feature builder is given a view containing a ground-truth key
- **THEN** it raises an error naming the key

### Requirement: Unusual panel values do not distort the probability
A panel value in an alternate unit SHALL be converted to the usual unit before use, a missing value SHALL be represented by an indicator, and a value no patient could have SHALL be treated as missing for the model.

#### Scenario: A panel unit that is not the usual one
- **WHEN** one panel value is given in its alternate unit (the dataset itself always writes the panel in the usual unit, so this is a robustness check) and everything else is equal
- **THEN** the probability differs from the usual-unit record's by at most 0.01

#### Scenario: Missing lab
- **WHEN** a panel value is null
- **THEN** the probability is still returned and the report carries a missing-value warning for that lab

#### Scenario: An impossible panel value
- **WHEN** a panel value is a decimal-shifted or negative value no patient could have
- **THEN** the probability differs by at most 0.01 from the same record with that lab treated as missing, and the report carries an `impossible_value` warning for the lab

### Requirement: Training uses the train split without dev, and is reproducible
Training SHALL use only train-split records that are not dev ids, with all randomness seeded. Two runs with the same data, configuration and seed SHALL produce byte-identical model files. Choosing between model families and settings SHALL use dev only, and the choice SHALL be recorded.

#### Scenario: Protected data is refused
- **WHEN** training is given a record from `test`, `adversarial` or the dev ids
- **THEN** it stops with an error naming the record and writes no model

#### Scenario: Same seed, same model
- **WHEN** training is run twice with the same seed
- **THEN** the two model files have the same hash

#### Scenario: Every run is tracked
- **WHEN** a training run finishes
- **THEN** MLflow holds its parameters, seed, data hash, dev metrics with intervals and the model file, and the run id is written next to the model

### Requirement: Probabilities are calibrated
The classifier SHALL return a probability between 0 and 1 that is calibrated on data not used to fit the model weights, with an expected calibration error on dev of at most 0.0643 (the project's target) reported with its interval. Probabilities MUST NOT be clamped to a narrow range: the 5th percentile of the reported probabilities on dev SHALL be at most 0.10 and the 95th percentile at least 0.60 (the true probabilities on dev run from 0.03 to 0.85 at those percentiles).

#### Scenario: Calibration on dev
- **WHEN** the classifier is scored on dev
- **THEN** AUC, Brier score, log loss and ECE are reported with 95% intervals, and each is stated against targets v1 as clearly met, not distinguishable or clearly not met

#### Scenario: The probabilities use the range
- **WHEN** the dev probabilities are summarised
- **THEN** the report gives their 5th and 95th percentiles

### Requirement: The report is valid and its uncertainty follows the probability
For every record the classifier system SHALL return a valid scored report. `uncertain` SHALL be true exactly when the probability lies in [0.4, 0.6], and `symptoms` SHALL come from the note reader.

#### Scenario: Uncertain follows the probability
- **WHEN** the dev reports are checked
- **THEN** every report with a probability in [0.4, 0.6] has `uncertain` true and every other report has it false

### Requirement: The report contains only real values and is deterministic
`labs_used` SHALL list only values present in the panel, with the panel's unit. Evidence SHALL be 2 to 5 short statements citing the record's own values, and the disclaimer SHALL say it is not medical advice. Repeated runs on the same record SHALL give the identical report.

#### Scenario: Determinism
- **WHEN** the matched-pair subset is run for three trials
- **THEN** the three reports for each record are identical, the consistency mean SD is 0 and pass^3 is 1

#### Scenario: No invented values and no unsafe text
- **WHEN** the final runs are graded
- **THEN** the fabrication rate is 0, the safety pass rate is 1 and the parse failure rate is 0

### Requirement: Panel data-quality checks
The system SHALL emit a `missing_value` warning for a null panel value and an `impossible_value` warning for a panel value no patient could have, one per lab, and no warning for a problem that is not there.

#### Scenario: Missing and impossible values
- **WHEN** a panel has a null value and a decimal-shifted value
- **THEN** the report has exactly one `missing_value` and one `impossible_value` warning, each naming its lab

### Requirement: Note data-quality checks
The system SHALL emit a `unit_mismatch` warning for a lab that the note states in an alternate unit instead of the usual one, a `contradiction` warning where the note states a lab value that disagrees with the panel after unit conversion by more than 1%, and a `note_flag_disagreement` warning where the note's own mentions of one symptom conflict. It MUST NOT emit a warning for a problem that is not there.

#### Scenario: Data-quality recall on dev
- **WHEN** the classifier system is scored on dev
- **THEN** recall for missing values, unit mismatches and contradictions is reported with intervals against the 0.5 target, and the exact-match rate is reported

#### Scenario: A clean record
- **WHEN** a record has no data problem
- **THEN** its data-quality list is empty

### Requirement: The classifier is small and fast on CPU
The model files SHALL total less than 10 MB, loading and predicting SHALL need only CPU, and the 95th percentile time to produce one report on a laptop CPU in one thread SHALL be less than 100 ms, excluding model loading.

#### Scenario: Latency
- **WHEN** 500 dev records are run one at a time
- **THEN** the report gives the median and 95th percentile time per record and the model size

### Requirement: The comparison with the frontier baseline is paired and honest
The classifier SHALL be scored on `test` and `adversarial` exactly once each with `--final`, after the model is fixed on dev, and compared with the frontier baseline on the same patients. For AUC, Brier score and log loss the report SHALL give the paired difference with a 95% interval from a bootstrap that resamples patients, and SHALL state that the classifier is better, worse or not distinguishable.

#### Scenario: One look at the protected splits
- **WHEN** a second final run of the classifier is requested for the same model hash
- **THEN** it is refused unless explicitly forced, and a forced run is recorded and warned about

#### Scenario: Paired difference
- **WHEN** the comparison report is written
- **THEN** each of AUC, Brier and log loss has the classifier value, the frontier value, the paired difference with its 95% interval and a plain-language verdict

### Requirement: A model card states what the model is
The repository SHALL contain a model card for the classifier giving its intended use (a fictional-disease demo, not medical advice), its data, the train and dev split, the held-out results, its known weaknesses and the synthetic-data notice.

#### Scenario: Model card present and current
- **WHEN** the test suite runs
- **THEN** the model card names the hash of the committed model file, and a mismatch fails the suite
