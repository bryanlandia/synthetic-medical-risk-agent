## MODIFIED Requirements

### Requirement: A free-text tab sends one message
A free-text assistant view, reached from "Behind the demo", SHALL take free text and send it, as it is, to the same route, and show the same card. Each send SHALL be a single, independent request: the page MUST NOT keep or send earlier messages or replies.

#### Scenario: No history
- **WHEN** two messages are sent one after the other
- **THEN** the second request contains only the second message and the first result is replaced

### Requirement: The model card is shown and checked against the running model
A view reached from "Behind the demo" SHALL show the committed model card rendered without its metadata block, and SHALL compare the model hash in the card with the hash the running service reports, showing whether they match.

#### Scenario: Matching and mismatching hashes
- **WHEN** the service reports the card's hash, and then a different hash
- **THEN** the view shows a match, and then a warning that the card does not describe the running model

### Requirement: An About tab describes the project
The page SHALL have an "About this project" view, reachable from every other view through "Behind the demo", that shows a project description written in markdown from a committed content file. It SHALL render every heading, paragraph, list, table and link in the file. The page MUST NOT fetch the description from the agent service.

#### Scenario: Every heading in the file is on the page
- **WHEN** the About view is opened
- **THEN** each second-level heading in the content file is shown as a heading, in the file's order

### Requirement: Every screen says the disease is fictional
Every screen SHALL show the persistent demo strip and a title that states the disease is fictional. The page MUST NOT claim FHIR, vendor or real-system integration.

#### Scenario: The title is on every tab
- **WHEN** the queue, a case and each Behind the demo view are opened
- **THEN** the title stating that the disease is fictional is visible without scrolling

#### Scenario: No integration is claimed
- **WHEN** the text of any view is read
- **THEN** it does not claim HL7, FHIR or a vendor's software

### Requirement: The funder is named and marked fictional
The About text and a footer shown on every screen SHALL state that the project is funded by the Kessler Family Foundation, a fictional foundation, to improve diagnosis and outcomes for Velorin-Kessler Syndrome. The foundation MUST NOT appear in any request, report or workflow text.

#### Scenario: The footer is on every tab
- **WHEN** each screen is opened
- **THEN** the footer names the Kessler Family Foundation and says it is fictional

#### Scenario: The foundation is not in the data path
- **WHEN** a check is run and the request body and the report are searched for the foundation's name
- **THEN** it is not found

## REMOVED Requirements

### Requirement: The chart page runs the check on the chart's contents
**Reason**: The page is now a queue of cases; a check runs when a case is first opened.
**Migration**: Replaced by "Opening a case shows the chart beside the packet" in `review-workspace`.

### Requirement: The message sent is visible
**Reason**: The sent-message control moves into the case view.
**Migration**: Covered by "Opening a case shows the chart beside the packet" in `review-workspace`.

### Requirement: Demo patients come from the dev split and carry no answer
**Reason**: Four sample patients are replaced by 30 seeded cases.
**Migration**: Replaced by "The 30 cases come from the dev split by a seeded rule" in `review-workspace`.

### Requirement: The chart page offers a scan-readiness packet
**Reason**: The packet is no longer a panel under the chart; the supervisor reviews it in the case view.
**Migration**: Replaced by "Opening a case shows the chart beside the packet" and "The supervisor decides" in `review-workspace`.

### Requirement: The packet view shows status, evidence and gaps plainly
**Reason**: Moved into the case view with the same content.
**Migration**: Covered by "Opening a case shows the chart beside the packet" in `review-workspace`.

### Requirement: Demo sign-off, copy and print
**Reason**: The demo sign-off becomes the supervisor's Release decision with a released packet.
**Migration**: Replaced by "The supervisor decides" and "A released packet reads like a request" in `review-workspace`.
