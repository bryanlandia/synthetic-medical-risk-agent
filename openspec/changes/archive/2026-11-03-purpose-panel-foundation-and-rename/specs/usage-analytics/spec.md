## MODIFIED Requirements

### Requirement: Clicks are counted by element name
A click on a navigation item, the "How it works" menu, a case in the queue, a status filter, a decision (Release, Return, Close), the confirm or Reset demo control, the help control, dismissing the intro panel, the "message sent" expander, Copy, Print, an example button, the Send button or a link that leaves the site SHALL send one event naming the element. Names SHALL come from a fixed set, with only a case's two-digit ordinal for a case and only the host for outbound links. Typing, pointer movement and clicks elsewhere MUST NOT be sent, and the page MUST NOT use automatic capture.

#### Scenario: A named click
- **WHEN** a visitor opens a case
- **THEN** one event names that click with the case's ordinal, and clicking empty page space sends nothing
