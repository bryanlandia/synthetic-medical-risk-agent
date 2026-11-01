## MODIFIED Requirements

### Requirement: A committed fictional policy defines six criteria
The repository SHALL contain one fictional coverage policy for a K-17 tracer PET-CT, stating that it is fictional and not a real payer's policy, with an id that names its version. It SHALL define criteria C1 to C6 and nothing else may decide a criterion. C1: at least 2 of Velorin index above 120 mg/dL, Tarnic acid above 360 umol/L and Dorrin ratio above 1.25. C2: tremor present and at least one other symptom present. C3: symptoms for 6 weeks or more. C4: other explanations considered. C5: no PET-CT or comparable imaging in the last 12 months. C6: specialist evaluation. The policy MUST NOT quote a model coefficient, and the model's probability and range SHALL NOT decide any criterion. The policy SHALL state that its thresholds are fictional and that meeting them says nothing about any patient.

#### Scenario: The policy is the single source
- **WHEN** the criteria table is built for any record
- **THEN** it has exactly six rows, C1 to C6, with the policy's wording, and changing the model's probability alone changes no row's status

#### Scenario: No coefficients
- **WHEN** the policy document is searched for any classifier coefficient or intercept
- **THEN** none is found

#### Scenario: Thresholds are one SD above the typical value
- **WHEN** the policy's three C1 thresholds are compared with the lab table
- **THEN** each equals the lab's usual mean plus one standard deviation, in the lab's usual unit, and a test fails if either changes without the other

#### Scenario: The version is named
- **WHEN** the policy is loaded
- **THEN** its id is `fictional-k17-pet-ct-v2` and `/healthz` reports the same id

### Requirement: C1 is judged from the labs on the chart, after unit conversion
C1 SHALL count the labs among Velorin index, Tarnic acid and Dorrin ratio whose value, converted to the lab's usual unit, is strictly above the policy's threshold for that lab. It SHALL be met when at least 2 count, unmet when fewer than 2 can still count after every unreported lab among the three is assumed above its threshold, and unknown otherwise. A lab that is not reported SHALL be listed as a gap to obtain. A value flagged as impossible by the data-quality check SHALL be treated as not reported. The lab's own reference range SHALL NOT decide C1. The evidence for each lab SHALL state its value as written with its unit, whether it is above the policy threshold, the threshold, and the lab's reference range.

#### Scenario: Two high labs
- **WHEN** Velorin index is above 120 mg/dL and Tarnic acid is above 360 umol/L (here 125 and 365)
- **THEN** C1 is met and cites `lab:velorin_index` and `lab:tarnic_acid`

#### Scenario: Above the policy threshold but inside the lab's range
- **WHEN** Velorin index is 125 mg/dL, inside its reference range of 70 to 130
- **THEN** it counts toward C1, and its evidence text says it is above the policy threshold of 120 mg/dL and gives the reference range

#### Scenario: Exactly at the threshold
- **WHEN** Velorin index is exactly 120 mg/dL
- **THEN** it does not count toward C1

#### Scenario: The evidence does not call a lab high or low
- **WHEN** a lab is above its reference range
- **THEN** it counts only if it is also above the policy threshold, and the evidence text does not call it "high" or "low"

#### Scenario: One high lab and one not reported
- **WHEN** one of the three labs is above its threshold, another is not, and the third is not reported
- **THEN** C1 is unknown and the third lab is a gap

#### Scenario: Value in the alternate unit
- **WHEN** the Velorin index is written in mmol/L and its converted value is above 120 mg/dL
- **THEN** it counts toward C1, and the cited value is the one as written with its unit

#### Scenario: Cannot be met
- **WHEN** two of the three labs are not above their thresholds and the third is not reported
- **THEN** C1 is unmet

#### Scenario: Impossible value
- **WHEN** a Dorrin ratio of 9.0 (outside plausibility bounds) is on the chart
- **THEN** it does not count toward C1 and the lab is listed as a gap
