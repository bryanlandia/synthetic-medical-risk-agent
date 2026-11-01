## ADDED Requirements

### Requirement: The chart page offers a scan-readiness packet
The chart page SHALL offer a "Prepare PET-CT packet" action for the selected patient with a yes, no or not-yet-answered control for each of C3 to C6, all starting as not yet answered. It SHALL send one request through the app's server route with the chart's message and the answers, and show the criteria table, the gaps, the summary and its source. No answer SHALL be pre-filled from the note or the model.

#### Scenario: Default answers
- **WHEN** the packet view is opened for any patient
- **THEN** C3 to C6 show not yet answered and the first packet shows them as unknown gaps

#### Scenario: One request
- **WHEN** the action is pressed
- **THEN** exactly one request is made, its message equals the patient's stored message, and its answers equal the controls

### Requirement: The packet view shows status, evidence and gaps plainly
Each criterion row SHALL show its policy wording, a status of met, unmet or unknown, and its cited evidence as the chart's values with units. Unknown rows SHALL show what would settle them. Unmet rows SHALL show the evidence factually and a clinician rationale field the page never fills. The summary SHALL show whether it came from the model or the template.

#### Scenario: Citations are visible
- **WHEN** a met criterion is shown
- **THEN** each cited lab or symptom appears beside it with the value read from the chart

#### Scenario: Rationale is empty
- **WHEN** a packet has an unmet criterion
- **THEN** the rationale field is empty and has a label saying it is for the clinician's own words

### Requirement: Demo sign-off, copy and print
The packet view SHALL offer a sign-off button labelled as a demo. After it is pressed the packet SHALL be read-only, labelled "drafted by tool, reviewed by clinician (demo)", with a copy and a print action. Every state of the view SHALL show the synthetic-data banner, and printing SHALL include it.

#### Scenario: Locked after sign-off
- **WHEN** sign-off is pressed
- **THEN** the answer controls and rationale field are read-only and the label is shown

#### Scenario: Banner in print
- **WHEN** the print view is rendered
- **THEN** it contains the synthetic-data banner and "not medical advice"

### Requirement: The packet page does not hold secrets or other fields
The browser SHALL reach the packet only through the app's server route, which holds the secret and the service address, and the route SHALL pass on only the whitelisted packet fields. The page MUST NOT offer any control that edits a recorded value, and MUST NOT use the words "approved", "denied", "eligible" or "qualifies" for a packet.

#### Scenario: Only whitelisted fields
- **WHEN** the service response has an extra field
- **THEN** the route does not pass it to the page

#### Scenario: No verdict words
- **WHEN** the packet view text is read for any demo patient
- **THEN** none of those words appears
