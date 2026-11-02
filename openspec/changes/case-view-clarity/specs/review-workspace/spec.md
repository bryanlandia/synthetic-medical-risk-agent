## MODIFIED Requirements

### Requirement: The page explains what the packet is for
The queue SHALL open with a plain-language panel titled "What is this packet for?" that says: the confirmatory scan (a K-17 PET-CT) is expensive, so insurers ask for documentation before they pay; an incomplete request, or one that does not point to its evidence, is sent back, which delays the patient and causes rework; the tool assembles the packet by checking the chart against the insurer's criteria, showing the evidence for each and listing what is missing; and the supervisor decides what to do with it while the tool decides nothing about care or coverage. The same text SHALL be reachable from every case through a help control. The terms PET-CT, prior authorization and packet SHALL each have a short hint where they first appear; the insurer's conditions SHALL be called "coverage criteria" in plain text, without a hint. The text MUST NOT use the words approved, denied, eligible or qualifies.

#### Scenario: The panel is the first thing on the queue
- **WHEN** a visitor opens the page for the first time
- **THEN** the panel is visible above the queue and its text names the scan, the insurer's coverage criteria, the evidence, the missing items, the supervisor's decision and that the tool decides nothing about care or coverage

#### Scenario: Help from a case
- **WHEN** the help control is pressed in a case
- **THEN** a dialog shows the same text and closes with the keyboard

#### Scenario: The panel can be put away and brought back
- **WHEN** the panel is dismissed and the page is reloaded
- **THEN** the panel stays dismissed, the help control still opens its text, and Reset demo shows the panel again

#### Scenario: No verdict words
- **WHEN** the panel, the help dialog and the hints are read
- **THEN** none of approved, denied, eligible or qualifies appears

### Requirement: The visitor works a queue of 30 prepared cases
The queue SHALL list 30 cases, each with its request code, patient id, insurer, preparing clinician, received date, time and time zone (for example "2 Nov 2026, 07:45 ET", fictional and the same for every visitor), the number of lab flags, the first line of the note, how many of the four preparer answers are complete, and a status chip of New, In review, Returned, Released or Closed. Status SHALL also be shown by text, not only by colour. A filter by status SHALL be available. The queue MUST NOT show a risk estimate or a criterion status for a case that has not been opened.

#### Scenario: Thirty cases, all New at first
- **WHEN** the page is opened with no saved progress
- **THEN** 30 rows are shown, each with the fields above, and every status is New

#### Scenario: Nothing is computed for an unopened case
- **WHEN** the queue is shown and no case has been opened
- **THEN** no request has been sent to the packet route and no row shows a probability or a met/unmet/unknown status

#### Scenario: Filtering
- **WHEN** the Returned filter is chosen after one case has been returned
- **THEN** only that case is listed

#### Scenario: Received has a date and a zone
- **WHEN** the queue is shown
- **THEN** each row's received value has a date, a time and a time zone, and is the same whatever zone the visitor's browser is in

### Requirement: Opening a case shows the chart beside the packet
Opening a case SHALL show the chart (each lab with its value, unit, reference range and flag, and the note headed "Clinical note") beside the packet: the six criteria with status and cited evidence, the gaps, the checked summary and where it came from, the model's estimate of the risk of Velorin-Kessler syndrome (fictional), stated as such, with its range, as context only, and the preparing clinician's four answers. A labelled, keyboard-operable disclosure ("Show the message sent to the service" / "Hide ...", with a visible indicator) SHALL show the exact message sent to the service. On first open exactly one request SHALL be made to the packet route, with the case's stored message and its preparer answers; its result SHALL be kept in the browser so reopening the case makes no request. Opening a case that is New SHALL set it to In review.

#### Scenario: One request on first open
- **WHEN** a New case is opened
- **THEN** exactly one request is made, its message equals the case's stored message and its answers equal the preparer answers, and the status becomes In review

#### Scenario: Reopening costs nothing
- **WHEN** the same case is closed and opened again
- **THEN** no further request is made and the same packet is shown

#### Scenario: Citations are visible
- **WHEN** a met criterion is shown
- **THEN** each lab or symptom it cites appears beside it with the value from the chart

#### Scenario: The answers are the preparer's, not the supervisor's
- **WHEN** the case view is read
- **THEN** the four answers are labelled as entered by the preparing clinician (simulated) and have no control that changes them

#### Scenario: A service error is explained
- **WHEN** the packet route answers 429 or 503
- **THEN** the case shows the existing plain explanation, stays New or In review, and offers a retry

#### Scenario: The estimate says what it estimates
- **WHEN** the estimate is read
- **THEN** it names Velorin-Kessler syndrome (fictional) as what is estimated, gives the percentage and range, and says it decides no criterion

#### Scenario: The sent message can be opened
- **WHEN** the sent-message disclosure is focused and operated with the keyboard
- **THEN** its label changes from Show to Hide, its indicator turns, and the exact message is shown

#### Scenario: The note is named
- **WHEN** the chart is read
- **THEN** the note is headed "Clinical note"

### Requirement: Demo notes are quiet and say what is pretend
A persistent strip on every screen SHALL say that everything is invented: the patients, the disease, the insurers and the policy, and that it is not medical advice. Each simulated element SHALL carry a small "Demo" chip with a muted note beside it: the role of supervisor and the preparing clinicians (the preparer's answers carry their "simulated" heading instead of a note); the shared fictional policy; the release (nothing is transmitted); the cover sheet's insurer, code and audit trail; the return note (goes to a pretend clinician); and the saved progress with its reset. After a release, a note SHALL say what happens next in real life (the insurer reviews the packet and responds, sometimes asking for more) and that none of it is simulated. The notes MUST NOT be dismissible banners over the work, and MUST NOT mention costs, savings or model accuracy.

#### Scenario: The strip is on every screen
- **WHEN** the queue, a case, a released packet and each Behind the demo view are opened
- **THEN** the strip is visible without scrolling

#### Scenario: Each simulated element is marked
- **WHEN** a case is opened and a release dialog is shown
- **THEN** a Demo chip with a note is beside the policy checklist and the release dialog, and the preparer answers are headed as simulated

#### Scenario: What happens next
- **WHEN** a case is released
- **THEN** the packet view includes the note that the insurer would review it and respond, and that none of that is simulated

#### Scenario: No costs or accuracy in the flow
- **WHEN** the queue, a case and a released packet are read
- **THEN** they contain no dollar amount, no word such as savings, and no model accuracy figure

### Requirement: The preparing clinicians and insurers are fictional
Each case SHALL name one of ten fictional insurers, a fictional preparing clinician and a fictional request code, assigned by a seeded rule so the same case always shows the same ones. Every mention of an insurer SHALL be marked fictional. The names MUST NOT be real insurers, real clinicians or real organisations, and MUST NOT include personal identifiers.

#### Scenario: Stable assignment
- **WHEN** the cases file is regenerated
- **THEN** each case has the same insurer, preparer, code, date and time as before

#### Scenario: Ten insurers are used
- **WHEN** the 30 cases are read
- **THEN** at least 6 distinct insurers appear, all from the committed list of ten

## ADDED Requirements

### Requirement: The page shows what produced each part
Each block of the case view and of a released packet SHALL carry a small label saying what produced it: the classifier model (the risk estimate), the note reader (a small model that reads the clinical note; shown on the criterion that comes from the note, not on the note itself), code (lab-threshold rules, criterion statuses and the checks on the summary), the language model (the summary draft) or the fixed template when the summary fell back to it, the simulated preparer (the C3 to C6 answers) and the supervisor (the decision). The checklist SHALL have a Source column naming, for each criterion, whether it comes from the chart's labs, the clinical note or the preparer's answer. A key titled "What produced this page?" SHALL be reachable from the queue and from every case, and the free-text view SHALL name the guards, the agent and the classifier it uses, closing with Escape and returning focus, and SHALL be built from the same table as the labels. Labels and key MUST NOT state an accuracy figure, a cost or a verdict word, and MUST say that the data and the disease are invented.

#### Scenario: Each block is labelled
- **WHEN** a case is opened and its packet is shown
- **THEN** the estimate carries the classifier label, the checklist carries the code label and its C2 source carries the note reader label, the answers carry the simulated preparer label and the summary carries the language model label

#### Scenario: A template summary is labelled as such
- **WHEN** the packet's summary source is the template
- **THEN** the summary carries the template label and not the language model label

#### Scenario: The checklist names its sources
- **WHEN** the checklist is read
- **THEN** C1 shows the chart's labs, C2 the clinical note, and C3 to C6 the preparer's answer

#### Scenario: The key
- **WHEN** the key is opened from the queue or a case
- **THEN** it explains each label in plain words, closes with Escape, and returns focus to the control that opened it

#### Scenario: Nothing about accuracy or cost
- **WHEN** the labels and the key are read
- **THEN** they contain no accuracy figure, dollar amount, savings word or verdict word
