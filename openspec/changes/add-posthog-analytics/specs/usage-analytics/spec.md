# Spec Delta

## Purpose

Defines what the demo page records about visits, what it must never record, how a visitor is told and can opt out, and when recording is switched off.

## ADDED Requirements

### Requirement: Analytics is off unless configured
The page SHALL start analytics and recording only when a PostHog project key is configured for that build. With no key, the page MUST make no request to any analytics host, load no analytics code, and show no recording notice.

#### Scenario: Local and test runs record nothing
- **WHEN** the page is built and opened with no project key
- **THEN** no request leaves the site's own address for analytics and no recording notice is shown

### Requirement: Visits are anonymous
The page MUST NOT identify a visitor, and MUST NOT store an identifier in cookies, local storage or session storage. Each visit SHALL be recorded as its own anonymous session.

#### Scenario: No browser storage
- **WHEN** a visit is recorded
- **THEN** analytics writes no cookie and no local or session storage entry, and makes no identify call

### Requirement: Typed text, messages and results are never captured
Events and recordings MUST NOT contain the text a visitor types, the message sent to the agent, the agent's reply or the report. Recordings SHALL block the free-text tab's text box and result and mask all text inputs. Events SHALL carry only labels: a tab name, a demo patient's slug, an example's name, a coarse result kind.

#### Scenario: A free-text send
- **WHEN** a visitor types a message, sends it and reads the result
- **THEN** no captured event contains any of the typed text, the reply or the probability, and the free-text tab's panel carries the marker that blocks it from recordings

### Requirement: Visitors are told, and can opt out
Every screen SHALL carry a one-line notice that visits and screen sessions are recorded and that typed text is not, with a control that stops recording for that visitor at once. The page SHALL honor Do Not Track and Global Privacy Control by not recording.

#### Scenario: Opting out
- **WHEN** a visitor presses the opt-out control
- **THEN** no further analytics request is made in that visit

#### Scenario: Do Not Track
- **WHEN** the browser sends Do Not Track or Global Privacy Control
- **THEN** nothing is recorded and no analytics request is made

### Requirement: Events go through the site's own address
The browser SHALL send analytics requests to a path on the site's own origin, which the server forwards to PostHog, so the PostHog address is not requested by the browser directly.

#### Scenario: First-party requests only
- **WHEN** analytics is on and a visit is recorded
- **THEN** every analytics request goes to the site's own origin

### Requirement: Recipients can be told apart by a link parameter
The page SHALL record a `ref` query parameter, when present, as a property of the visit, so the owner can give different people different links. The value SHALL be limited in length and characters before it is recorded.

#### Scenario: A tagged link
- **WHEN** the page is opened with `?ref=ode`
- **THEN** the visit is recorded with `ref` equal to `ode`, and an oversized or unusual value is trimmed or dropped
