# Spec Delta

## Purpose

Defines the CPU note reader that turns a clinical note into the five symptom readings and the lab values the note itself states, with no API call, so the classifier and its report can use the note without a language model.

## ADDED Requirements

### Requirement: Symptom readings come from the note alone
The reader SHALL return, for each of the five symptoms (`tremor`, `fatigue`, `photophobia`, `joint_stiffness`, `dizziness`), one of `present`, `possible`, `absent` or `not_mentioned`, using only the note text. It MUST NOT read the lab panel, the patient id or any ground-truth field, and it MUST run with no network access and no API key.

#### Scenario: Reading from the note
- **WHEN** a note says "denies shaking" and "feels dizzy" and does not mention light sensitivity
- **THEN** the reader returns `absent` for tremor, `present` for dizziness and `not_mentioned` for photophobia

#### Scenario: Hedged statements
- **WHEN** a note says a symptom is "possible", "occasionally" or "?"
- **THEN** the reader returns `possible` for that symptom

#### Scenario: Works offline
- **WHEN** the reader runs with the network disabled and no `ANTHROPIC_API_KEY` set
- **THEN** it returns readings for every note

### Requirement: The reader is accurate on records it has not seen
The reader SHALL be trained only on the train split without the dev ids, and SHALL reach a symptom-reading accuracy of at least 0.95 on dev, scored by the project's symptom-reading grader. A reader below 0.95 MUST be reported as not meeting this requirement.

#### Scenario: Dev accuracy
- **WHEN** the reader is scored on the 500 dev records
- **THEN** the symptom-reading accuracy and its 95% interval are reported, and 0.95 or more is required

#### Scenario: Training excludes dev and protected splits
- **WHEN** training starts
- **THEN** every training record id is in the train split and none is a dev id, and a run that includes a `test` or `adversarial` record is refused with an error naming the record

### Requirement: The reader is held to account on an unseen documentation setting
The reader SHALL be trained on three of the four documentation settings (shorthand, EHR template, AI scribe, copy-forward) in turn and scored on the held-out fourth, and the four held-out accuracies SHALL be reported. A held-out accuracy below 0.90 for any setting MUST be reported as a finding, with the settings and phrases that failed.

#### Scenario: Held-out setting report
- **WHEN** the leave-one-setting-out experiment is run
- **THEN** a table gives the symptom-reading accuracy and its interval for each held-out setting next to the in-distribution accuracy

### Requirement: Stated lab values are read from the note
The reader SHALL extract, for each lab the note states, the lab, the value and the unit as written, so that the report can detect a stated value that disagrees with the panel. A note value that cannot be read with confidence MUST be left out, not guessed.

#### Scenario: A stated value
- **WHEN** a note line reads "Serum K-17 (K17): 15.4 mg/dL"
- **THEN** the reader returns serum_k17, 15.4 and mg/dL

#### Scenario: No invented values
- **WHEN** a note states no lab values
- **THEN** the reader returns an empty list

### Requirement: Instructions in a note have no effect
The reader SHALL treat note text as data. Text addressed to the system, such as an addendum asking for a particular result, MUST NOT change the symptom readings beyond what the note states about the patient.

#### Scenario: Injection pairs
- **WHEN** every catalog injection is appended to each dev note and the note is read with and without it
- **THEN** the symptom readings are identical for at least 95% of the pairs, and every difference is listed
