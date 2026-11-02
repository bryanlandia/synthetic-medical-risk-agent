# review-workspace Specification

## Purpose
TBD - created by archiving change supervisor-review-workspace. Update Purpose after archive.

## Requirements

### Requirement: The page explains what the packet is for
The queue SHALL open with a plain-language panel titled "What is this packet for?" that says: the confirmatory scan (a K-17 PET-CT) is expensive, so insurers ask for documentation before they pay; an incomplete request, or one that does not point to its evidence, is sent back, which delays the patient and causes rework; the tool assembles the packet by checking the chart against the insurer's criteria, showing the evidence for each and listing what is missing; and the supervisor decides what to do with it while the tool decides nothing about care or coverage. The same text SHALL be reachable from every case through a help control. The terms PET-CT, prior authorization, packet and criteria SHALL each have a short hint where they first appear. The text MUST NOT use the words approved, denied, eligible or qualifies.

#### Scenario: The panel is the first thing on the queue
- **WHEN** a visitor opens the page for the first time
- **THEN** the panel is visible above the queue and its text names the scan, the insurer's criteria, the evidence, the missing items, the supervisor's decision and that the tool decides nothing about care or coverage

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
The queue SHALL list 30 cases, each with its request code, patient id, insurer, preparing clinician, received time, the number of lab flags, the first line of the note, how many of the four preparer answers are complete, and a status chip of New, In review, Returned, Released or Closed. Status SHALL also be shown by text, not only by colour. A filter by status SHALL be available. The queue MUST NOT show a risk estimate or a criterion status for a case that has not been opened.

#### Scenario: Thirty cases, all New at first
- **WHEN** the page is opened with no saved progress
- **THEN** 30 rows are shown, each with the fields above, and every status is New

#### Scenario: Nothing is computed for an unopened case
- **WHEN** the queue is shown and no case has been opened
- **THEN** no request has been sent to the packet route and no row shows a probability or a met/unmet/unknown status

#### Scenario: Filtering
- **WHEN** the Returned filter is chosen after one case has been returned
- **THEN** only that case is listed

### Requirement: Opening a case shows the chart beside the packet
Opening a case SHALL show the chart (each lab with its value, unit, reference range and flag, and the note) beside the packet: the six criteria with status and cited evidence, the gaps, the checked summary and where it came from, the model's estimate and range as context only, and the preparing clinician's four answers. A control SHALL show the exact message sent to the service. On first open exactly one request SHALL be made to the packet route, with the case's stored message and its preparer answers; its result SHALL be kept in the browser so reopening the case makes no request. Opening a case that is New SHALL set it to In review.

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

### Requirement: The supervisor decides: Release, Return or Close
Each opened case SHALL offer three decisions. Release SHALL be disabled while any criterion is unknown, with the reason stated, and when any criterion is unmet SHALL require the supervisor's own rationale of at least 20 characters before it is enabled. Return with a note SHALL require a note of at least 5 characters and set the status to Returned. Close, criteria not met SHALL set the status to Closed. A Released or Closed case SHALL be read-only except for its stored packet view. A Returned case SHALL offer "Reopen this request", which sets it back to In review and adds a Reopened event, so it can be decided again. No decision MUST transmit anything, and the tool MUST NOT write, suggest or edit the rationale or the note.

#### Scenario: Release with every criterion met
- **WHEN** all six criteria are met
- **THEN** Release is enabled without a rationale, and confirming it sets the status to Released

#### Scenario: Release is blocked by an unknown criterion
- **WHEN** a criterion is unknown
- **THEN** Release is disabled, the gap is named as the reason, and Return is offered

#### Scenario: Release with an unmet criterion needs a rationale
- **WHEN** a criterion is unmet and the rationale field is empty or shorter than 20 characters
- **THEN** Release is disabled until the supervisor has typed a rationale of at least 20 characters

#### Scenario: Returning with a note
- **WHEN** a note of at least 5 characters is entered and Return is confirmed
- **THEN** the case shows a Returned chip in the queue and the note is shown with the case

#### Scenario: A returned case can be reopened
- **WHEN** a Returned case is opened and Reopen this request is pressed
- **THEN** its status is In review, its return note is kept, and its timeline gains a Reopened event

#### Scenario: Nothing is sent
- **WHEN** any decision is confirmed
- **THEN** no request is made except to the packet route on first open, and the dialog says nothing is transmitted

### Requirement: A released packet reads like a request
A Released case SHALL show a cover sheet (the fictional insurer, a fictional request code, the patient id and the requested study), the six criteria with their evidence, the gaps (none, for a release), the checked summary, the supervisor's rationale marked as their own words, and an audit timeline of what was prepared and what the supervisor did with times. Copy and print SHALL be offered, and the printed view SHALL carry the demo and synthetic-data notice.

#### Scenario: The cover sheet
- **WHEN** a case is released and its packet is shown
- **THEN** the cover sheet names the insurer, request code, patient id and requested study, each marked fictional

#### Scenario: The audit timeline
- **WHEN** a case was opened, returned, reopened and released
- **THEN** the timeline lists the preparer's entry and each supervisor action in order with times

#### Scenario: The printed view
- **WHEN** the print view is rendered
- **THEN** it holds the packet and the notice, and omits the queue and the controls

### Requirement: Progress is kept in this browser and can be reset
The page SHALL keep every case's status, packet, note, rationale and audit events in the browser's local storage, so a reload restores them, including Returned cases and their notes. It SHALL store nothing on the server and send nothing from storage except through the packet route. A Reset demo control SHALL, after confirmation, clear the stored progress and restore all 30 cases to New. Saved progress made for different case data or a different policy SHALL be discarded rather than shown.

#### Scenario: Returned survives a reload
- **WHEN** a case is returned with a note and the page is reloaded
- **THEN** the queue still shows it as Returned and the note is shown with the case

#### Scenario: Reset
- **WHEN** Reset demo is confirmed
- **THEN** every case is New, no packet or note is kept, and the explanation panel is shown again

#### Scenario: Stale progress
- **WHEN** stored progress names a different cases hash or policy id than the page
- **THEN** it is discarded and the queue starts fresh

#### Scenario: Cancelling the reset
- **WHEN** Reset demo is pressed and then cancelled
- **THEN** nothing changes

### Requirement: Demo notes are quiet and say what is pretend
A persistent strip on every screen SHALL say that everything is invented: the patients, the disease, the insurers and the policy, and that it is not medical advice. Each simulated element SHALL carry a small "Demo" chip with a muted note beside it: the role of supervisor and the preparing clinicians; the preparer's answers; the shared fictional policy; the release (nothing is transmitted); the cover sheet's insurer, code and audit trail; the return note (goes to a pretend clinician); and the saved progress with its reset. After a release, a note SHALL say what happens next in real life (the insurer reviews the packet and responds, sometimes asking for more) and that none of it is simulated. The notes MUST NOT be dismissible banners over the work, and MUST NOT mention costs, savings or model accuracy.

#### Scenario: The strip is on every screen
- **WHEN** the queue, a case, a released packet and each Behind the demo view are opened
- **THEN** the strip is visible without scrolling

#### Scenario: Each simulated element is marked
- **WHEN** a case is opened and a release dialog is shown
- **THEN** a Demo chip with a note is beside the preparer answers, the policy checklist and the release dialog

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
- **THEN** each case has the same insurer, preparer, code and time as before

#### Scenario: Ten insurers are used
- **WHEN** the 30 cases are read
- **THEN** at least 6 distinct insurers appear, all from the committed list of ten

### Requirement: The 30 cases come from the dev split by a seeded rule
The cases file SHALL hold 30 cases chosen from the dev split by a seeded rule written in the repository. Of the 30, 8 to 10 SHALL have C1 met, 6 to 7 C1 unknown and the rest C1 unmet, and the set SHALL include at least 3 with a unit mismatch, 2 with a contradiction, 3 borderline probabilities and 3 with a lab not reported, and tremor present, hedged, absent and not mentioned. Each case SHALL carry its chart, its pre-rendered message equal to the harness's rendering, and preparer answers drawn by a seeded rule so that at least 15 are fully answered yes, at least 3 hold a no and at least 3 hold an unanswered item. The file MUST NOT hold any ground-truth field, and a test SHALL fail if the file differs from what the builder writes.

#### Scenario: The file is current and clean
- **WHEN** the cases test runs
- **THEN** every patient id is in the dev split, every message equals the harness's rendering, no ground-truth key appears, and a fresh build equals the committed file byte for byte

#### Scenario: The mix
- **WHEN** the 30 cases are summarised by their C1 status, data problems and preparer answers
- **THEN** the counts meet the ranges above

#### Scenario: Some cases are releasable and some are not
- **WHEN** the packets are built for the 30 cases
- **THEN** every dev patient with both C1 and C2 met is included, so at least 3 are fully releasable (all six criteria met, only three exist in the dev split), at least 5 are blocked by an unknown criterion, and at least 5 have an unmet criterion that a rationale could address

### Requirement: The interface is a coherent, accessible Material design
The web app SHALL use Material UI with one theme (colour, type, spacing, shape) for every screen, load no font, script or image from another site, and keep working with the keyboard alone: every control reachable and operable, dialogs closing with Escape and returning focus, and visible focus. Status and flags SHALL not rely on colour alone, and text and interactive elements SHALL meet a 4.5:1 contrast ratio against their background.

#### Scenario: Keyboard only
- **WHEN** a case is opened, a decision made and the dialog closed using only the keyboard
- **THEN** each step is possible and focus returns to the control that opened the dialog

#### Scenario: Nothing from another site
- **WHEN** the production build's pages are loaded
- **THEN** no request goes to another site for a font, script or image (the analytics request, when enabled, is the one existing exception)

#### Scenario: Contrast
- **WHEN** the theme's text and chip colours are checked against their backgrounds
- **THEN** each pair meets 4.5:1

### Requirement: Criteria are worded so a Yes means the criterion holds
Wherever the page shows the wording of a criterion the preparing clinician attested (the preparer answers, the checklist, the released packet and the copied text), a Yes answer SHALL mean the criterion holds. C5 SHALL be shown as "The last PET-CT or comparable imaging was more than 12 months ago, or there has been none." and MUST NOT be shown with a leading negation. The change is display only: the stored answers, the criterion statuses and the policy are unchanged.

#### Scenario: C5 in the preparer answers
- **WHEN** a case is opened and the preparer answers are read
- **THEN** C5 is shown in the positive wording, and a case whose C5 answer is Yes shows C5 as met in the checklist

#### Scenario: C5 in the checklist and the released packet
- **WHEN** the checklist, a released packet and its copied text are read
- **THEN** each shows the same positive wording for C5 and none contains "No PET-CT"

#### Scenario: Other criteria are untouched
- **WHEN** C1 to C4 and C6 are shown
- **THEN** their wording equals the policy text
