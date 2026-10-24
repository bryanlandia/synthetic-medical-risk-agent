# Spec Delta

## Purpose

Defines how fictional patients, a fictional disease, and its ground-truth labels are generated, so that downstream training and evals can measure accuracy, calibration and robustness against known truth. No real patient data is ever used.

## ADDED Requirements

### Requirement: Fictional data labeling
Every generated artifact SHALL identify itself as synthetic and the disease as fictional. This covers each data file, each record, and the dataset documentation.

#### Scenario: Record carries the synthetic marker
- **WHEN** any record is read from any generated split
- **THEN** it contains a field marking it as synthetic, and the disease name is a fictional one that matches no real condition

#### Scenario: Dataset documentation states the constraint
- **WHEN** a user opens the dataset documentation in `data_gen/`
- **THEN** it states that all data is synthetic, the disease is fictional, and the data must not be used for real medical purposes

### Requirement: Fictional patient features
The generator SHALL sample each patient with between 6 and 10 fictional lab values, each with a fictional name, unit and reference range, plus a set of binary symptom flags. The flags are ground truth that feeds the scoring rule and are not part of the model-visible input.

#### Scenario: Lab names are fictional
- **WHEN** the lab definitions are inspected
- **THEN** no lab name maps to a real clinical test (for example "Velorin index", not "glucose")

#### Scenario: Feature counts are within bounds
- **WHEN** a cohort is generated
- **THEN** every patient has a value or an explicit missing marker for each lab, and the lab count is between 6 and 10

### Requirement: Model input excludes ground truth
Each record SHALL expose two views. The model-visible input view contains the lab panel (with its unit and missing-value issues) and the clinical note. The ground-truth view contains the symptom flags, true probability and label. Symptoms SHALL reach a model only through the note.

#### Scenario: Input view has no flags
- **WHEN** the input view of any record is serialized
- **THEN** it contains no symptom flag fields, no true probability and no label

#### Scenario: Ground truth is kept alongside
- **WHEN** the full record is read for evaluation
- **THEN** the ground-truth view contains every symptom flag, the true probability and the label for that patient

### Requirement: Hidden scoring rule defines ground truth
The disease SHALL be defined by a hidden scoring rule that maps a patient's features to a true probability of disease. The rule SHALL be a pure function of the structured ground-truth features (labs and symptom flags), never of the note text.

#### Scenario: True probability stored with each record
- **WHEN** a record is generated
- **THEN** it stores the true probability produced by the rule, a value in the closed interval 0 to 1

#### Scenario: Rule is independent of notes
- **WHEN** a patient's note is regenerated or altered while labs and flags are held fixed
- **THEN** the patient's true probability and label are unchanged

#### Scenario: Rule is not shipped to the model or agent
- **WHEN** the artifacts consumed by training and the agent are inspected
- **THEN** they contain features, labels and (for evaluation only) true probabilities, but not the rule's coefficients

### Requirement: Labels sampled from true probability
Each patient's binary label SHALL be sampled from a Bernoulli draw using the true probability, so that label noise is irreducible and calibration can be measured.

#### Scenario: Labels match probabilities in aggregate
- **WHEN** a cohort of at least 10,000 patients is generated and patients are grouped into ten equal-width true-probability bins
- **THEN** in every bin the observed positive rate is within 0.03 of the mean true probability

#### Scenario: Prevalence is configurable and reported
- **WHEN** a cohort is generated
- **THEN** the realized prevalence is reported with the dataset and falls within 0.02 of the configured target for cohorts of at least 10,000

### Requirement: Reproducible generation
Generation SHALL be deterministic given a seed and a generator version. Both SHALL be recorded in the output.

#### Scenario: Same seed gives identical structured data
- **WHEN** the generator is run twice with the same seed, configuration and version
- **THEN** the structured fields (labs, flags, true probability, label, split) are byte-identical across runs

#### Scenario: Different seed gives different data
- **WHEN** the generator is run with two different seeds
- **THEN** the cohorts differ and no patient identifier collides across the two outputs

#### Scenario: Provenance is recorded
- **WHEN** a dataset is produced
- **THEN** its manifest records the seed, generator version, configuration, and record counts per split

### Requirement: Train, random-test and adversarial splits
The generator SHALL produce three disjoint splits: a train split, a random test split drawn from the same distribution as train, and an adversarial split of deliberately hard cases.

#### Scenario: Splits are disjoint
- **WHEN** the three splits are produced
- **THEN** no patient identifier appears in more than one split

#### Scenario: Random test matches train distribution
- **WHEN** train and random test are compared on realized prevalence and on each lab's mean
- **THEN** prevalence differs by at most 0.02 and each lab mean differs by less than 0.1 standard deviations

#### Scenario: Adversarial split covers the required case types
- **WHEN** the adversarial split is produced
- **THEN** each record is tagged with one or more case types and the split contains at least 50 records of each type: borderline (true probability between 0.4 and 0.6), impossible lab values, missing labs, unit mismatch, note contradicting labs, note disagreeing with the true symptom flags (`note_flag_disagreement`), and prompt injection in note text

### Requirement: Impossible and edge-case values are labeled
Cases with physiologically impossible or out-of-range values SHALL be generated only in the adversarial split, and each SHALL carry a tag identifying the defect so evals can check handling.

#### Scenario: Impossible values are tagged
- **WHEN** a record contains a lab value outside the fictional plausible range
- **THEN** it belongs to the adversarial split and carries an `impossible_value` tag naming the lab

#### Scenario: Train and random test are clean
- **WHEN** train and random test records are validated
- **THEN** every present lab value lies within its fictional plausible range
