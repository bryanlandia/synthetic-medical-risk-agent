## REMOVED Requirements

### Requirement: The page has two scenarios under one title
**Reason**: The requirement is replaced by one with the same content that names the menu "How it works" in its text and scenarios, which a MODIFIED block cannot do because it may not rename a scenario.
**Migration**: See "The page has two scenarios and a How it works menu".

## ADDED Requirements

### Requirement: The page has two scenarios and a How it works menu
The page SHALL be titled VK-Check, and its main navigation SHALL offer the review queue, which is shown first, "Estimate a risk", and "How it works". Each scenario SHALL show its own subtitle, and the review queue's SHALL remain "Supervisor review". "How it works" SHALL hold the model card and the About text and nothing else.

#### Scenario: The first screen
- **WHEN** the page is opened
- **THEN** the review queue is shown and the navigation offers the queue, Estimate a risk and How it works

#### Scenario: The How it works menu
- **WHEN** the How it works menu is opened
- **THEN** it lists the model card and the About text, and no assistant view

#### Scenario: Each scenario names itself
- **WHEN** the queue and then Estimate a risk are opened
- **THEN** the title VK-Check is visible in both, each with its own subtitle, and both say the disease is fictional without scrolling
## MODIFIED Requirements

### Requirement: A free-text tab sends one message
A free-text box, inside the Estimate a risk scenario and collapsed by default, SHALL take free text and send it, as it is, to the same route, and show the same card. Each send SHALL be a single, independent request: the page MUST NOT keep or send earlier messages or replies. The free-text box MUST NOT be reached from "How it works".

#### Scenario: No history
- **WHEN** two messages are sent one after the other
- **THEN** the second request contains only the second message and the first result is replaced

#### Scenario: Where it lives
- **WHEN** How it works is opened and then Estimate a risk is opened
- **THEN** the free-text box is found only in Estimate a risk, collapsed

### Requirement: The model card is shown and checked against the running model
A view reached from "How it works" SHALL show the committed model card rendered without its metadata block, and SHALL compare the model hash in the card with the hash the running service reports, showing whether they match.

#### Scenario: Matching and mismatching hashes
- **WHEN** the service reports the card's hash, and then a different hash
- **THEN** the view shows a match, and then a warning that the card does not describe the running model

### Requirement: An About tab describes the project
The page SHALL have an "About this project" view, reachable from every other view through "How it works", that shows a project description written in markdown from a committed content file. It SHALL render every heading, paragraph, list, table and link in the file. The page MUST NOT fetch the description from the agent service.

#### Scenario: Every heading in the file is on the page
- **WHEN** the About view is opened
- **THEN** each second-level heading in the content file is shown as a heading, in the file's order

### Requirement: Every screen says the disease is fictional
Every screen SHALL show the persistent demo strip and a title that states the disease is fictional. The page MUST NOT claim FHIR, vendor or real-system integration.

#### Scenario: The title is on every tab
- **WHEN** the queue, a case and each How it works view are opened
- **THEN** the title stating that the disease is fictional is visible without scrolling

#### Scenario: No integration is claimed
- **WHEN** the text of any view is read
- **THEN** it does not claim HL7, FHIR or a vendor's software
