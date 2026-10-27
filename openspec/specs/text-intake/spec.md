# text-intake Specification

## Purpose

Defines how one free-text message becomes the record view the classifier reads, deterministically and without a language model, so that no lab value the classifier sees was typed or changed by a model.

## Requirements

### Requirement: A message becomes a record view
Intake SHALL turn one message into a view with a lab panel of one entry per lab (value and unit) and a note, and nothing else. The note SHALL be the whole message. A lab the message does not state SHALL have a null value. The same message SHALL always give the same view.

#### Scenario: A message with some labs
- **WHEN** the message states a Velorin index and a Tarnic acid and no other lab
- **THEN** the view has eight panel entries, two with values and six null, and its note is the message text

#### Scenario: A message with no labs
- **WHEN** the message states no lab value
- **THEN** all eight panel values are null and the classifier still returns a report with a missing-value warning for each lab

### Requirement: Lab values are read from the message and never invented
Every non-null panel value SHALL equal a number the message writes next to that lab's name or abbreviation, after converting an alternate unit to the usual unit. Intake MUST NOT infer, round, estimate or fill in a value, and a value it cannot read with confidence SHALL be left null.

#### Scenario: Every panel value is in the message
- **WHEN** a test renders 500 dev records as messages and runs intake on each
- **THEN** every non-null panel value is a number written in its message, and none is absent from it

#### Scenario: Ambiguous wording is left out
- **WHEN** a message mentions a lab by name with no number next to it
- **THEN** that lab's panel value is null

### Requirement: Alternate units, repeats and impossible values are passed on honestly
A value stated in an alternate unit SHALL be converted to the usual unit in the panel and the report SHALL carry a unit-mismatch warning for that lab. When a lab is stated more than once, the first stated value SHALL be the panel value and a later value that disagrees SHALL produce a contradiction warning. A value no patient could have SHALL be passed on as written so that the classifier flags it and ignores it.

#### Scenario: Alternate unit
- **WHEN** the message states "Serum K-17 15.4 mg/dL"
- **THEN** the panel value is 15.4 divided by 3.91 in mmol/L and the report has a `unit_mismatch` warning for serum_k17

#### Scenario: A repeated lab that disagrees
- **WHEN** the message states "Velorin index 104 mg/dL" and later "Velorin index 140 mg/dL"
- **THEN** the panel value is 104 and the report has a `contradiction` warning for velorin_index

#### Scenario: An impossible value
- **WHEN** the message states a Velorin index of 1040 mg/dL
- **THEN** the report has an `impossible_value` warning for velorin_index and the probability equals the one with that lab missing, within 0.01

### Requirement: The text path agrees with the structured path
For a record whose panel and note are rendered into one message by the evals' documented format, the probability through intake and the classifier SHALL equal the probability the classifier gives the structured record, within 0.001, for at least 95% of dev records. Every record outside that tolerance SHALL be listed with the reason.

#### Scenario: Agreement on dev
- **WHEN** the 500 dev records are scored both ways
- **THEN** the share within 0.001 is reported with its count, and at least 95% agree

#### Scenario: Exceptions are explained
- **WHEN** a dev record differs by more than 0.001
- **THEN** it appears in the report with the lab or symptom reading that differs
