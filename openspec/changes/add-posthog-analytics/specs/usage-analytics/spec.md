# Spec Delta

## Purpose

Defines what the demo page counts about visits and clicks, what it must never collect, how a visitor is told and can opt out, and when counting is switched off.

## ADDED Requirements

### Requirement: Analytics is off unless configured
The page SHALL start analytics only when a PostHog project key is configured for that build. With no key, the page MUST make no request to any analytics host, load no analytics code, and show no analytics notice.

#### Scenario: Local and test runs count nothing
- **WHEN** the page is built and opened with no project key
- **THEN** no request leaves the site's own address for analytics and no analytics notice is shown

### Requirement: Visits are anonymous and leave nothing in the browser
The page MUST NOT identify a visitor, and MUST NOT write cookies, local storage or session storage for analytics. Visitors SHALL be counted without a stored identifier.

#### Scenario: No browser storage
- **WHEN** a visit is counted
- **THEN** analytics writes no cookie and no local or session storage entry, and makes no identify call

### Requirement: Each page load is counted once
The page SHALL send one page view per load, carrying the `ref` value when present, so that the owner can see how many visits there are and where they came from.

#### Scenario: One page view
- **WHEN** the page is opened and a visitor switches tabs
- **THEN** exactly one page view is sent for that load

### Requirement: Clicks are counted by element name
A click on a tab, a demo patient, the Run V-K check button, the "message sent" expander, an example button, the Send button, the opt-out control or a link that leaves the site SHALL send one event naming the element. Names SHALL come from a fixed set, with only the host for outbound links. Typing, pointer movement and clicks elsewhere MUST NOT be sent, and the page MUST NOT use automatic capture.

#### Scenario: A named click
- **WHEN** a visitor presses Run V-K check
- **THEN** one event names that button, and clicking empty page space sends nothing

### Requirement: Typed text, messages and results are never collected
Events MUST NOT contain the text a visitor types, the message sent to the agent, the agent's reply, the report or the probability. Events SHALL carry only labels: a tab name, a demo patient's slug, an example's name, a coarse result kind (scored, declined or error).

#### Scenario: A free-text send
- **WHEN** a visitor types a message, sends it and reads the result
- **THEN** no event contains any of the typed text, the reply or the probability

### Requirement: The screen is not recorded
The page MUST NOT record screen sessions and MUST NOT load a recording script.

#### Scenario: No recorder
- **WHEN** analytics is on and a visit is counted
- **THEN** no request is made for a session-recording script and none is sent

### Requirement: Visitors are told, and can opt out
Every screen SHALL carry a one-line notice that visits and clicks are counted anonymously and that typed text is not collected, with a control that stops counting for that visitor at once. The page SHALL honor Do Not Track and Global Privacy Control by counting nothing.

#### Scenario: Opting out
- **WHEN** a visitor presses the opt-out control
- **THEN** no further analytics request is made in that visit

#### Scenario: Do Not Track
- **WHEN** the browser sends Do Not Track or Global Privacy Control
- **THEN** nothing is counted and no analytics request is made

### Requirement: Events go through the site's own address
The browser SHALL send analytics requests to a path on the site's own origin, which the server forwards to PostHog, so the PostHog address is not requested by the browser directly.

#### Scenario: First-party requests only
- **WHEN** analytics is on and a visit is counted
- **THEN** every analytics request goes to the site's own origin

### Requirement: Recipients can be told apart by a link parameter
The page SHALL record a `ref` query parameter, when present, as a property of the visit's events, so the owner can give different people different links. The value SHALL be reduced to a short, safe set of characters before it is recorded.

#### Scenario: A tagged link
- **WHEN** the page is opened with `?ref=ode`
- **THEN** the visit's events carry `ref` equal to `ode`, and an oversized or unusual value is reduced or dropped
