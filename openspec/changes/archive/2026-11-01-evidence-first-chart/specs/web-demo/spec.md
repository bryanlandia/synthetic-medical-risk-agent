## ADDED Requirements

### Requirement: The chart shows reference ranges and flags
The chart SHALL show each lab's reference range and an H or L flag when the value is outside it, judged on the value converted to the lab's usual unit. A lab not reported SHALL show no flag. The range and flag SHALL come from the committed demo-patient file, not from the agent.

#### Scenario: A flagged lab
- **WHEN** a patient's Velorin index is above its reference range
- **THEN** its row shows the range and an H flag

#### Scenario: A value in the alternate unit
- **WHEN** the demo patient with a unit mismatch is shown
- **THEN** the flag is judged after conversion to the usual unit and the row shows the unit as written

#### Scenario: Not reported
- **WHEN** a lab is not reported
- **THEN** its row shows no flag

### Requirement: The report card shows the range and the gaps
The report card SHALL show the probability with its range, labelled as the range if missing results are obtained, and a list of the gaps with the largest swings first, each marked when obtaining it could change the routing. It MUST NOT offer any control that edits a recorded value.

#### Scenario: A patient with a missing lab
- **WHEN** the check is run on the demo patient with a missing lab
- **THEN** the card shows a range wider than a point, and a gap entry for that lab

#### Scenario: The range is not called a confidence interval
- **WHEN** the card text is read
- **THEN** it does not use the phrase "confidence interval"

#### Scenario: Only whitelisted fields reach the page
- **WHEN** the route returns a response
- **THEN** only the interval and gaps fields the page shows are passed on, as with the existing fields
