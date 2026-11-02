# Spec Delta

## ADDED Requirements

### Requirement: The page has two scenarios under one title
The page SHALL be titled VK-Check, and its main navigation SHALL offer the review queue, which is shown first, "Estimate a risk", and "Behind the demo". Each scenario SHALL show its own subtitle, and the review queue's SHALL remain "Supervisor review". "Behind the demo" SHALL hold the model card and the About text and nothing else.

#### Scenario: The first screen
- **WHEN** the page is opened
- **THEN** the review queue is shown and the navigation offers the queue, Estimate a risk and Behind the demo

#### Scenario: Behind the demo
- **WHEN** the Behind the demo menu is opened
- **THEN** it lists the model card and the About text, and no assistant view

#### Scenario: Each scenario names itself
- **WHEN** the queue and then Estimate a risk are opened
- **THEN** the title VK-Check is visible in both, each with its own subtitle, and both say the disease is fictional without scrolling

### Requirement: Estimate a risk has its own introduction
The Estimate a risk scenario SHALL open with a short introduction, in plain words, of what the controls do, that the patient is invented, and that the number is an estimate from a fictional disease's model and not advice. The queue's introduction and help SHALL NOT appear in it.

#### Scenario: The introduction
- **WHEN** Estimate a risk is opened
- **THEN** its introduction is visible, states that the patient is invented, and does not contain the queue's introduction text

## MODIFIED Requirements

### Requirement: A free-text tab sends one message
A free-text box, inside the Estimate a risk scenario and collapsed by default, SHALL take free text and send it, as it is, to the same route, and show the same card. Each send SHALL be a single, independent request: the page MUST NOT keep or send earlier messages or replies. The free-text box MUST NOT be reached from "Behind the demo".

#### Scenario: No history
- **WHEN** two messages are sent one after the other
- **THEN** the second request contains only the second message and the first result is replaced

#### Scenario: Where it lives
- **WHEN** Behind the demo is opened and then Estimate a risk is opened
- **THEN** the free-text box is found only in Estimate a risk, collapsed
