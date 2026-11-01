# web-demo Specification

## Purpose

Defines the public demo page: a mock patient chart that runs the risk check on the chart's contents, the free-text tab for trying the agent's guards, the model-card tab, and the server route that is the browser's only way to the agent.

## Requirements

### Requirement: The chart page runs the check on the chart's contents
The page SHALL show a mock patient chart (labs and a note) for one of the demo patients, selectable from the list, with a "Run V-K check" button. The button SHALL send one message built from the chart's non-null labs, with name and usual unit, followed by the note, and nothing else, and SHALL show the result in a report card beside the chart.

#### Scenario: A check on a demo patient
- **WHEN** a visitor selects a patient and presses the button
- **THEN** exactly one request is made, its message equals the patient's stored message, and the report card shows the result

### Requirement: The message sent is visible
The chart SHALL have an expander showing the exact message the check sends, so a visitor can see the agent receives only the chart's contents. The displayed text SHALL be the text sent.

#### Scenario: The expander matches the request
- **WHEN** the expander is opened and the check is run
- **THEN** the message in the request body is identical to the text in the expander

### Requirement: The report card shows the report and the reply
For a scored message the card SHALL show the probability, whether the result is uncertain, the evidence strings, the data-quality warnings, the labs read and the reply with its disclaimer. For a declined message it SHALL show the reason and the fixed message, and no report.

#### Scenario: The unit-mismatch patient
- **WHEN** the check is run on the demo patient with a unit mismatch and a missing lab
- **THEN** the card lists a unit-mismatch warning and a missing-value warning

#### Scenario: A decline
- **WHEN** the free-text tab sends a treatment question
- **THEN** the card shows a decline with its reason and no probability

### Requirement: A free-text tab sends one message
A second tab SHALL take free text and send it, as it is, to the same route, and show the same card. Each send SHALL be a single, independent request: the page MUST NOT keep or send earlier messages or replies.

#### Scenario: No history
- **WHEN** two messages are sent one after the other
- **THEN** the second request contains only the second message and the first result is replaced

### Requirement: Demo patients come from the dev split and carry no answer
The demo patients SHALL be a small committed set taken from the dev split, each with its chart and its pre-rendered message. The file MUST NOT contain a ground-truth field, and it SHALL be equal to what the evaluation harness renders for those patients.

#### Scenario: The file is current and clean
- **WHEN** the demo-patient test runs
- **THEN** every patient id is in the dev split, every message equals the harness's rendering, and no ground-truth key appears

### Requirement: The browser never holds the secret or the service address
The browser SHALL call only a server route of the web app. The route SHALL add the shared secret and the visitor address, forward the message, and return only the fields the page shows. The secret and the agent's address MUST NOT appear in any file sent to the browser.

#### Scenario: Nothing leaks to the client
- **WHEN** the production build's browser-visible files are searched
- **THEN** neither the shared secret nor the agent service's address is found

### Requirement: Service errors are explained
The route and page SHALL turn each service error into a clear message: 413 and 422 (the message is too long or empty), 429 with the wait from `Retry-After`, 503 (the demo's daily budget is used up, try tomorrow), 502 and timeouts (the model is unavailable), and 401 (the demo is misconfigured, without detail). No error shows a raw upstream body.

#### Scenario: Rate limited
- **WHEN** the service answers 429 with `Retry-After: 30`
- **THEN** the page tells the visitor to wait about 30 seconds

#### Scenario: Daily budget used
- **WHEN** the service answers 503
- **THEN** the page says the daily budget is used up and to come back tomorrow

### Requirement: The model card is shown and checked against the running model
A tab SHALL show the committed model card rendered without its metadata block, and SHALL compare the model hash in the card with the hash the running service reports, showing whether they match.

#### Scenario: Matching and mismatching hashes
- **WHEN** the service reports the card's hash, and then a different hash
- **THEN** the tab shows a match, and then a warning that the card does not describe the running model

### Requirement: An About tab describes the project
The page SHALL have a tab named "About this project", reachable from every other tab, that shows a project description written in markdown from a committed content file. It SHALL render every heading, paragraph, list, table and link in the file. The page MUST NOT fetch the description from the agent service.

#### Scenario: Every heading in the file is on the page
- **WHEN** the About tab is opened
- **THEN** each second-level heading in the content file is shown as a heading, in the file's order

### Requirement: Links in the description are safe
Links in the About text SHALL open in a new tab without giving the new page access to this one, and the About tab MUST NOT load scripts, images or fonts from another site.

#### Scenario: A link opens safely
- **WHEN** the About tab contains a link to another address
- **THEN** the link opens in a new tab with `noopener` and `noreferrer`, and the tab makes no request to another site

### Requirement: Every screen says the disease is fictional
Every screen SHALL show a title that states the disease is fictional. The page MUST NOT claim FHIR, vendor or real-system integration.

#### Scenario: The title is on every tab
- **WHEN** each tab is opened
- **THEN** the title stating that the disease is fictional is visible without scrolling

#### Scenario: No integration is claimed
- **WHEN** the text of any tab is read
- **THEN** it does not claim HL7, FHIR or a vendor's software

### Requirement: The About tab tells the project's story
The About text SHALL state, in plain words, that the disease is fictional and often overlooked, that caught early it is highly treatable, and that missed it becomes a degenerative neurological disease. It SHALL describe the pathway of screen, confirm and treat, say this project is the first stage, and name both costs of delay: the patient's time to diagnosis and the institution's rework and denials.

#### Scenario: The story sections are present
- **WHEN** the About tab is opened
- **THEN** its text contains the disease course, the three-stage pathway with this project marked as stage one, and a statement of the patient and institution costs of delay, each under a heading

#### Scenario: The story stays fictional
- **WHEN** the story sections of the About text are searched for treatment names, doses, any figure, and dollar or days-saved amounts
- **THEN** none is found

### Requirement: The funder is named and marked fictional
The About text and a footer shown on every tab SHALL state that the project is funded by the Kessler Family Foundation, a fictional foundation, to improve diagnosis and outcomes for Velorin-Kessler Syndrome. The foundation MUST NOT appear in any request, report or workflow text.

#### Scenario: The footer is on every tab
- **WHEN** each tab is opened
- **THEN** the footer names the Kessler Family Foundation and says it is fictional

#### Scenario: The foundation is not in the data path
- **WHEN** a check is run and the request body and the report are searched for the foundation's name
- **THEN** it is not found

### Requirement: The About text is accurate about the system
The About text SHALL describe the baseline as the prompted Haiku model with its measured AUC, SHALL call the chat service an assistant, and SHALL keep the notice that the LLM reviewer is not a clinician and a description of the guards.

#### Scenario: Known leftovers are fixed
- **WHEN** the About text is read
- **THEN** it does not say "prompted frontier models" for the Haiku result, does not call the chat service an agent, and includes the guards paragraph and the reviewer caveat

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
