## ADDED Requirements

### Requirement: Scored reports carry a sensitivity range
A scored report from the classifier system SHALL include `interval`: the lowest and highest probability the model gives over the plausible values of every unmeasured lab and every symptom the note does not mention. A symptom takes any of absent, possible or present.

#### Scenario: A complete record has a point range
- **WHEN** all eight labs are measured and every symptom is stated
- **THEN** the interval's lower and upper bounds equal the probability

#### Scenario: A missing lab widens the range
- **WHEN** one lab is not on the chart
- **THEN** the interval brackets the probability, its lower bound is at most the probability and its upper bound at least the probability, and it equals the lowest and highest probability found by trying every combination of that lab's two plausible end values

#### Scenario: Exact against brute force
- **WHEN** a record has up to six unmeasured findings
- **THEN** the reported bounds match a brute-force search over every end-value combination to within 1e-9

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
