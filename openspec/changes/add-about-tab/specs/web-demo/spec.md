# Spec Delta

## ADDED Requirements

### Requirement: An About tab describes the project
The page SHALL have a tab named "About this project", reachable from every other tab, that shows a project description written in markdown from a committed content file. It SHALL render every heading, paragraph, list, table and link in the file, and SHALL carry the same banner as every other tab. The page MUST NOT fetch the description from the agent service.

#### Scenario: Every heading in the file is on the page
- **WHEN** the About tab is opened
- **THEN** each second-level heading in the content file is shown as a heading, in the file's order, and the banner is visible

### Requirement: Links in the description are safe
Links in the About text SHALL open in a new tab without giving the new page access to this one, and the About tab MUST NOT load scripts, images or fonts from another site.

#### Scenario: A link opens safely
- **WHEN** the About tab contains a link to another address
- **THEN** the link opens in a new tab with `noopener` and `noreferrer`, and the tab makes no request to another site
