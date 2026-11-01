## ADDED Requirements

### Requirement: A committed fictional policy defines six criteria
The repository SHALL contain one fictional coverage policy for a K-17 tracer PET-CT, stating that it is fictional and not a real payer's policy. It SHALL define criteria C1 to C6 and nothing else may decide a criterion. C1: at least 2 of Velorin index, Tarnic acid and Dorrin ratio above their reference range. C2: tremor present and at least one other symptom present. C3: symptoms for 6 weeks or more. C4: other explanations considered. C5: no PET-CT or comparable imaging in the last 12 months. C6: specialist evaluation. The policy MUST NOT quote a model coefficient, and the model's probability and range SHALL NOT decide any criterion.

#### Scenario: The policy is the single source
- **WHEN** the criteria table is built for any record
- **THEN** it has exactly six rows, C1 to C6, with the policy's wording, and changing the model's probability alone changes no row's status

#### Scenario: No coefficients
- **WHEN** the policy document is searched for any classifier coefficient or intercept
- **THEN** none is found

### Requirement: Each criterion is met, unmet or unknown
Every criterion SHALL have exactly one status: met, unmet or unknown. A criterion is unknown when the evidence needed to decide it is missing, and nothing SHALL be filled in, inferred or worded around to make it met.

#### Scenario: Statuses are exhaustive
- **WHEN** the criteria table is built for any record and any set of answers
- **THEN** every row's status is one of met, unmet or unknown

### Requirement: C1 is judged from the labs on the chart, after unit conversion
C1 SHALL count the labs among Velorin index, Tarnic acid and Dorrin ratio whose value, converted to the lab's usual unit, is above its reference range. It SHALL be met when at least 2 count, unmet when fewer than 2 can still count after every unreported lab among the three is assumed high, and unknown otherwise. A lab that is not reported SHALL be listed as a gap to obtain. A value flagged as impossible by the data-quality check SHALL be treated as not reported.

#### Scenario: Two high labs
- **WHEN** Velorin index and Tarnic acid are above their reference ranges
- **THEN** C1 is met and cites `lab:velorin_index` and `lab:tarnic_acid`

#### Scenario: One high lab and one not reported
- **WHEN** one of the three labs is high, another is within range and the third is not reported
- **THEN** C1 is unknown and the third lab is a gap

#### Scenario: Value in the alternate unit
- **WHEN** the Velorin index is written in mmol/L and its converted value is above the range in mg/dL
- **THEN** it counts toward C1, and the cited value is the one as written with its unit

#### Scenario: Cannot be met
- **WHEN** two of the three labs are within range and the third is not reported
- **THEN** C1 is unmet

#### Scenario: Impossible value
- **WHEN** a Dorrin ratio of 9.0 (outside plausibility bounds) is on the chart
- **THEN** it does not count toward C1 and the lab is listed as a gap

### Requirement: C2 is judged from the note's symptom readings
C2 SHALL be met when tremor is read as present and at least one other symptom is read as present, unmet when tremor is read as absent or when no other symptom can still be present, and unknown otherwise. A symptom read as possible or not mentioned SHALL never count as present, and each such symptom SHALL produce a gap prompt naming it.

#### Scenario: Tremor and fatigue present
- **WHEN** the note states tremor and fatigue as present
- **THEN** C2 is met and cites `symptom:tremor` and `symptom:fatigue`

#### Scenario: Hedged tremor
- **WHEN** the note says tremor is possible
- **THEN** C2 is unknown and a gap prompt names tremor

#### Scenario: Tremor explicitly absent
- **WHEN** the note states no tremor
- **THEN** C2 is unmet

### Requirement: C3 to C6 come only from clinician answers
C3 to C6 SHALL be decided only by structured answers of yes, no or not yet answered, supplied with the request. Yes SHALL make a criterion met, no unmet and not yet answered unknown. No attestation SHALL be derived from the note, the model, a default or an earlier request, and an answer for a criterion outside C3 to C6, or a value other than yes, no or unanswered, SHALL be rejected.

#### Scenario: Nothing answered
- **WHEN** a packet is built with no attestation answers
- **THEN** C3 to C6 are unknown and each is a gap to attest

#### Scenario: The note claims history
- **WHEN** the note says "symptoms for 8 weeks, no prior imaging" and no answers are given
- **THEN** C3 and C5 are unknown

#### Scenario: An answer of no
- **WHEN** C5 is answered no
- **THEN** C5 is unmet

#### Scenario: A malformed answer
- **WHEN** an answer is "maybe", or names a criterion C7, or tries to set C1
- **THEN** the request is rejected and no packet is built

### Requirement: Every status carries citations that exist
Each met or unmet criterion SHALL list the evidence ids it rests on, and an id SHALL be one of `lab:<key>`, `symptom:<key>`, `attest:<C3..C6>` or `model:risk`, present in that packet's evidence list with the value as recorded. Evidence lists SHALL hold only values from the record, with the unit as written.

#### Scenario: Citations resolve
- **WHEN** a packet is built for any dev record
- **THEN** every cited id is in the packet's evidence list, and every lab value in the list equals the record's value within 1% after unit conversion

### Requirement: Gaps list what is missing and never alter the record
The packet SHALL list one gap per unknown criterion and, for each, what would settle it (a lab to obtain, a symptom to document, an attestation to give). A gap SHALL NOT change, replace or propose a recorded value.

#### Scenario: Gap per unknown
- **WHEN** a packet has 3 unknown criteria
- **THEN** it lists 3 gaps, one naming each criterion

#### Scenario: Gap recall
- **WHEN** records with a withheld lab or an unmentioned symptom are packeted
- **THEN** every criterion that depends on the withheld item is unknown and has a gap

### Requirement: Unmet criteria are listed factually and the rationale is the clinician's
Unmet criteria SHALL be listed with the evidence that makes them unmet and no advice. The packet SHALL offer a free-text rationale field, with a length cap of 1,000 characters, to request the scan anyway. The tool MUST NOT write, suggest or rewrite the rationale, MUST NOT state or imply that the request will be approved or denied, and MUST NOT give an eligibility verdict.

#### Scenario: Unmet C1
- **WHEN** C1 is unmet
- **THEN** the packet lists the labs and values that make it unmet and an empty clinician-only rationale field

#### Scenario: Rationale is passed through unchanged
- **WHEN** a clinician types a rationale
- **THEN** the signed-off packet shows it exactly, marked as the clinician's text, and the model never sees it

### Requirement: The evidence summary is drafted by a model and verified by code
The packet SHALL run one model step, with no tools, that drafts the evidence summary as structured sentences, each with a criterion id, a status and the evidence ids it cites. The model SHALL receive only the criteria table and evidence list. Code SHALL reject the draft, and the packet SHALL then use a summary built from fixed templates, when any sentence: has no citation or cites an id not in the evidence list; contains a number, lab or unit not found in its cited evidence; states a status different from the criteria table; or contains banned vocabulary (a diagnosis, treatment, urgency, an eligibility verdict such as qualifies, eligible, approved or denied, or wording coaching such as "phrase the request as"). The source of the summary SHALL be reported as `model` or `template`.

#### Scenario: A faithful draft
- **WHEN** the model's draft has cited sentences whose statuses and numbers match the table
- **THEN** it is shown and the source is `model`

#### Scenario: A sentence without a citation
- **WHEN** a draft sentence cites no evidence id
- **THEN** the template summary is used and the source is `template`

#### Scenario: An invented number
- **WHEN** a draft sentence says "Velorin index 165" and the cited lab is 142
- **THEN** the template summary is used

#### Scenario: A status contradiction
- **WHEN** a sentence says C1 is met and the table says unknown
- **THEN** the template summary is used

#### Scenario: Banned vocabulary
- **WHEN** a draft says "the patient qualifies" or names a medication
- **THEN** the template summary is used

#### Scenario: The model is unavailable
- **WHEN** the model call fails or times out
- **THEN** the template summary is used, the criteria table and gaps are still returned, and the failure is counted

### Requirement: Sign-off locks the packet as a demo
The packet SHALL offer a demo sign-off control, labelled as a demo, that locks the packet as "drafted by tool, reviewed by clinician (demo)" and offers copy and print. Every packet view SHALL state that all data is synthetic and the disease is fictional. The tool SHALL store nothing between requests.

#### Scenario: Sign-off
- **WHEN** the clinician presses the sign-off control
- **THEN** the packet is read-only, carries the demo label, and a copy or print is offered

#### Scenario: Notice present
- **WHEN** any packet view or printout is read
- **THEN** it contains the synthetic-data notice and "not medical advice"

### Requirement: The packet gives no medical advice or care gating
The packet and every text in it SHALL contain no diagnosis of a real disease, no treatment, medication or dose, and no statement that care should be delayed, withheld or prioritised. Criteria that are unmet or unknown MUST NOT be described as a reason not to scan.

#### Scenario: Safety grader
- **WHEN** every packet text field for the dev and adversarial sets is checked against the denylist and banned vocabulary
- **THEN** none matches

### Requirement: Costs are illustrative
Any cost figure shown with the packet SHALL be labelled illustrative and fictional, and SHALL NOT be presented as a saving or as a measured result.

#### Scenario: Cost label
- **WHEN** a cost figure is displayed
- **THEN** it is labelled illustrative and no word such as "saves" or "savings" appears with it
