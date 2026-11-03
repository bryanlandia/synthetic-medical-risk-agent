## MODIFIED Requirements

### Requirement: The page explains what the packet is for
The queue SHALL open with a plain-language panel titled "What are the review and packet for?". It SHALL say, first, why the tools exist: Velorin-Kessler syndrome (a fictional disease) is a neurological disorder that is treatable if caught early but becomes a debilitating and expensive disease if it is not, and the Kessler Family Foundation (also fictional) sponsors these tools to speed insurer coverage of the confirming scan and to aid diagnosis. It SHALL then say: the confirmatory scan (a K-17 PET-CT) is expensive, so insurers ask for documentation before they pay; an incomplete request, or one that does not point to its evidence, is sent back, which delays the patient and causes rework; the tool assembles the packet by checking the chart against the insurer's criteria, showing the evidence for each and listing what is missing; and the supervisor decides what to do with it while the tool decides nothing about care or coverage. The same text SHALL be reachable from every case through a help control. The terms PET-CT, prior authorization and packet SHALL each have a short hint where they first appear; the insurer's conditions SHALL be called "coverage criteria" in plain text, without a hint. The text MUST NOT use the words approved, denied, eligible or qualifies.

#### Scenario: The panel is the first thing on the queue
- **WHEN** a visitor opens the page for the first time
- **THEN** the panel is visible above the queue, headed "What are the review and packet for?", and its text names the early-treatable and costly-if-missed disease, the sponsoring foundation, the scan, the insurer's coverage criteria, the evidence, the missing items, the supervisor's decision and that the tool decides nothing about care or coverage

#### Scenario: The sponsor is named and marked fictional
- **WHEN** the panel is read
- **THEN** the Kessler Family Foundation is named as the sponsor of the tools, is marked fictional, and the text says the tools speed insurer coverage and aid diagnosis without saying the tool grants or refuses coverage

#### Scenario: Help from a case
- **WHEN** the help control is pressed in a case
- **THEN** a dialog shows the same text and closes with the keyboard

#### Scenario: The panel can be put away and brought back
- **WHEN** the panel is dismissed and the page is reloaded
- **THEN** the panel stays dismissed, the help control still opens its text, and Reset demo shows the panel again

#### Scenario: No verdict words
- **WHEN** the panel, the help dialog and the hints are read
- **THEN** none of approved, denied, eligible or qualifies appears

### Requirement: Demo notes are quiet and say what is pretend
A persistent strip on every screen SHALL say that everything is invented: the patients, the disease, the insurers and the policy, and that it is not medical advice. Each simulated element SHALL carry a small "Demo" chip with a muted note beside it: the role of supervisor and the preparing clinicians (the preparer's answers carry their "simulated" heading instead of a note); the shared fictional policy; the release (nothing is transmitted); the cover sheet's insurer, code and audit trail; the return note (goes to a pretend clinician); and the saved progress with its reset. After a release, a note SHALL say what happens next in real life (the insurer reviews the packet and responds, sometimes asking for more) and that none of it is simulated. The notes MUST NOT be dismissible banners over the work, and MUST NOT mention costs, savings or model accuracy.

#### Scenario: The strip is on every screen
- **WHEN** the queue, a case, a released packet and each How it works view are opened
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

