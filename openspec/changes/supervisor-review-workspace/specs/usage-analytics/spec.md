## MODIFIED Requirements

### Requirement: Clicks are counted by element name
A click on a navigation item, a case in the queue, a status filter, a decision (Release, Return, Close), the confirm or Reset demo control, the help control, the "message sent" expander, Copy, Print, an example button, the Send button or a link that leaves the site SHALL send one event naming the element. Names SHALL come from a fixed set, with only a case's two-digit ordinal for a case and only the host for outbound links. Typing, pointer movement and clicks elsewhere MUST NOT be sent, and the page MUST NOT use automatic capture.

#### Scenario: A named click
- **WHEN** a visitor opens a case
- **THEN** one event names that click with the case's ordinal, and clicking empty page space sends nothing

### Requirement: Typed text, messages and results are never collected
Events MUST NOT contain the text a visitor types (including a return note or a rationale), the message sent to the agent, the agent's reply, the report, a criterion's status, the probability or a patient id. Events SHALL carry only labels: a navigation name, a case ordinal, a decision kind, an example's name, a coarse result kind (scored, declined or error).

#### Scenario: A free-text send
- **WHEN** a visitor types a message, sends it and reads the result
- **THEN** no event contains any of the typed text, the reply or the probability

#### Scenario: A return note
- **WHEN** a supervisor types a note, returns a case and releases another with a rationale
- **THEN** no event contains the note, the rationale, a patient id or a criterion status

### Requirement: Visits are anonymous and leave nothing in the browser
The page MUST NOT identify a visitor, and MUST NOT write cookies, local storage or session storage for analytics. Visitors SHALL be counted without a stored identifier. The only thing the page keeps in local storage is the supervisor's own review progress, which carries no identifier, is never sent anywhere, and is written only after the visitor has acted (opened a case, dismissed the intro or decided); a visit that changes nothing writes nothing.

#### Scenario: No browser storage
- **WHEN** a visit is counted and the visitor only looks around
- **THEN** analytics writes no cookie and no local or session storage entry, and makes no identify call, and the page has written nothing either

#### Scenario: Progress is the only entry
- **WHEN** a visitor opens a case
- **THEN** the only entry in local storage is the review progress, which holds no identifier and none of the analytics state
