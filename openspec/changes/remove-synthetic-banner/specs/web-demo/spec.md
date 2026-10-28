# Spec Delta

## REMOVED Requirements

### Requirement: Every screen says what this is
**Reason**: The owner dropped the banner and the mock-EHR label; the title now carries the fictional status.
**Migration**: See "Every screen says the disease is fictional", which keeps the no-integration clause.

## ADDED Requirements

### Requirement: Every screen says the disease is fictional
Every screen SHALL show a title that states the disease is fictional. The page MUST NOT claim FHIR, vendor or real-system integration.

#### Scenario: The title is on every tab
- **WHEN** each tab is opened
- **THEN** the title stating that the disease is fictional is visible without scrolling

#### Scenario: No integration is claimed
- **WHEN** the text of any tab is read
- **THEN** it does not claim HL7, FHIR or a vendor's software

## MODIFIED Requirements

### Requirement: An About tab describes the project
The page SHALL have a tab named "About this project", reachable from every other tab, that shows a project description written in markdown from a committed content file. It SHALL render every heading, paragraph, list, table and link in the file. The page MUST NOT fetch the description from the agent service.

#### Scenario: Every heading in the file is on the page
- **WHEN** the About tab is opened
- **THEN** each second-level heading in the content file is shown as a heading, in the file's order
