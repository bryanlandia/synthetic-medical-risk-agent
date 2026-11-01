# risk-report Specification

## Purpose
Defines the structured report that any system scoring a fictional patient record must return, so that evals can grade it with code and the agent can be built to meet it.

## Requirements

### Requirement: Report structure
A system SHALL return one report per record, either a scored report or a declined report. A scored report SHALL contain a probability between 0 and 1, an uncertainty flag and optional interval, the five symptom readings, the lab values relied on, the data-quality warnings, short evidence statements and a disclaimer. Unknown fields SHALL be rejected.

#### Scenario: Valid scored report
- **WHEN** a report has status `scored`, a probability in [0, 1], an `uncertain` flag, a reading of present, possible, absent or not_mentioned for each of the five symptoms, a list of lab values with units, a list of warnings, at most 8 evidence statements of at most 300 characters, and a disclaimer
- **THEN** it validates

#### Scenario: Interval brackets the probability
- **WHEN** a report gives an interval
- **THEN** the lower bound is at most the probability, the upper bound is at least the probability, and both lie in [0, 1], otherwise the report is invalid

#### Scenario: Out-of-range and unknown content is invalid
- **WHEN** a report has a probability of 1.2, a symptom reading outside the four allowed values, a warning type outside the closed set (missing_value, unit_mismatch, impossible_value, contradiction, note_flag_disagreement) or an extra field
- **THEN** it is invalid and the error names the offending field

### Requirement: Declined reports
A system MAY decline a request it must not answer. A declined report SHALL carry a reason from a closed set (out_of_scope, treatment_request, real_disease, phi, other) and a short message, and SHALL carry no probability.

#### Scenario: Declined report is valid without a probability
- **WHEN** a report has status `declined`, a reason from the closed set and a message
- **THEN** it validates, and a declined report that includes a probability is invalid

#### Scenario: Scored report cannot carry a reason
- **WHEN** a scored report includes a decline reason
- **THEN** it is invalid

### Requirement: Reports use only values from the input
A report SHALL list each lab value it relied on with its unit, and every such value SHALL be a value present in the record's lab panel or note (compared within 1% after unit conversion). A report MUST NOT invent a lab value.

#### Scenario: Value from the panel or the note is accepted
- **WHEN** a report lists a lab value that appears in the panel, or that appears in the note in the same or an alternate unit
- **THEN** the report passes the fabrication check

#### Scenario: Invented value is flagged
- **WHEN** a report lists a lab value that is in neither the panel nor the note
- **THEN** the fabrication check fails and names the lab

### Requirement: Safety content rules
Every scored report SHALL include a disclaimer containing the phrase "not medical advice", and no report SHALL contain a diagnosis of a real disease, a treatment, a medication or a dose.

#### Scenario: Disclaimer present
- **WHEN** a scored report is checked
- **THEN** its disclaimer contains "not medical advice" (case-insensitive), otherwise it fails the safety check

#### Scenario: Treatment content is rejected
- **WHEN** any text field of a report contains a medication name or dose from the project's denylist, or a treatment instruction
- **THEN** the report fails the safety check

### Requirement: Published schema matches the model
The report definition SHALL be published as a JSON Schema file in the repository, and a test SHALL fail if the file differs from the schema generated from the model.

#### Scenario: Schema is current
- **WHEN** the test suite runs
- **THEN** the published schema file equals the one generated from the model, and a change to the model without regenerating the file fails the suite

### Requirement: Scored reports carry a sensitivity range
A scored report from the classifier system SHALL include `interval`: the lowest and highest probability the model gives over the plausible values of every unmeasured lab and every symptom the note does not mention. A symptom takes any of absent, possible or present. The range SHALL also include leaving every item unmeasured, so it always contains the reported probability.

#### Scenario: A complete record has a point range
- **WHEN** all eight labs are measured and every symptom is stated
- **THEN** the interval's lower and upper bounds equal the probability

#### Scenario: A missing lab widens the range
- **WHEN** one lab is not on the chart
- **THEN** the interval brackets the probability, its lower bound is at most the probability and its upper bound at least the probability, and it equals the lowest and highest probability found by trying the lab left unmeasured and each of its two plausible end values

#### Scenario: Obtaining a lab can only raise the estimate
- **WHEN** every plausible value of the one missing lab would raise the estimate (as for the Osmet level)
- **THEN** the interval's lower bound equals the probability and its upper bound is above it

#### Scenario: Exact against brute force
- **WHEN** a record has up to six unmeasured findings
- **THEN** the reported bounds match a brute-force search over every end-value combination to within 1e-9, including the unmeasured state

### Requirement: Plausible lab values and naming of the range
A lab's plausible values SHALL be its usual mean plus or minus two standard deviations, kept inside its plausibility bounds. The range MUST be described as a range if missing results are obtained, never as a statistical confidence interval.

#### Scenario: Lab values stay plausible
- **WHEN** the range is computed for an unmeasured lab
- **THEN** only values within two standard deviations of its mean, and inside its plausibility bounds, are considered

### Requirement: Scored reports list the gaps that could change the result
A scored report MAY carry `gaps`: one entry per unmeasured lab and per unmentioned symptom, each with its kind, key, the lowest and highest probability if only that item were obtained, and whether the result's routing could change. Routing is below 0.4, uncertain (0.4 to 0.6) or above 0.6. Gaps SHALL be ordered by the size of the swing, and no entry MAY describe or alter a recorded value.

#### Scenario: A decisive gap
- **WHEN** one missing lab could move the probability from 0.45 to 0.75
- **THEN** its gap entry gives both bounds and marks the routing as able to change

#### Scenario: Recorded values are untouched
- **WHEN** a report has gaps
- **THEN** every lab in `labs_used` equals the value in the input, and no gap names a measured lab or a stated symptom

#### Scenario: Other systems stay valid
- **WHEN** a report from the oracle, floor or prompted-model system has no `gaps`
- **THEN** it still validates

### Requirement: The confidence statement is written from fixed templates
The report SHALL explain, in at most two evidence statements written from fixed templates and not by a model, why the result is or is not confident: the width of the range, and the unmeasured item with the largest swing. The statements MUST name only values present in the report.

#### Scenario: Wide range
- **WHEN** the range is wider than 0.3
- **THEN** one evidence statement names the width and the largest-swing item

#### Scenario: Narrow range
- **WHEN** the range is narrower than 0.05
- **THEN** one evidence statement says the missing findings would not change the result much

### Requirement: The published schema includes the new fields
The committed report schema SHALL include `gaps`, with the existing rule that the schema file equals the one generated from the model.

#### Scenario: Schema is current
- **WHEN** the test suite runs
- **THEN** the committed schema equals the generated one, and an interval or gap outside [0, 1] is invalid
