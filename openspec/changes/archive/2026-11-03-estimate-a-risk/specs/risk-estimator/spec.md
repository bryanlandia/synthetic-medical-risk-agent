# Spec Delta

## Purpose

Defines the "Estimate a risk" scenario: a visitor sets made-up labs and symptoms with sliders and toggles, sees the classifier's estimate and what drove it, and can send the same patient to the assistant to see its guardrails act on a note they did not have to write.

## ADDED Requirements

### Requirement: Inputs are the eight labs and five symptoms, within limits
The scenario SHALL offer one control for each of the eight labs and each of the five symptoms and no other input. A lab control SHALL range over the lab's plausible range in the lab's usual unit and SHALL have a "not done" state; a symptom control SHALL have the states absent, possible and present.

#### Scenario: One control per input
- **WHEN** the scenario is opened
- **THEN** it shows eight lab controls with a not-done state and five symptom controls with three states, and no other control that changes the estimate

#### Scenario: A lab cannot leave its plausible range
- **WHEN** a lab control is moved to either end
- **THEN** its value is the lab's lowest or highest plausible value and never one outside it

### Requirement: The scenario opens on a borderline patient and can be reset
The scenario SHALL open on a prepared patient whose estimate lies inside the uncertain band (0.4 to 0.6), and a Reset control SHALL return every input to that patient. The prepared patient MUST be invented and MUST NOT be a queue case.

#### Scenario: First view
- **WHEN** the scenario is opened for the first time
- **THEN** the estimate shown is between 0.4 and 0.6 and its band is the uncertain band

#### Scenario: Reset
- **WHEN** inputs have been changed and Reset is pressed
- **THEN** every input and the estimate equal their first-view values

### Requirement: The estimate is the classifier's and is exact
The estimate shown SHALL be the committed classifier's probability for the inputs, computed by the service in `risk_model` without a language model, and SHALL equal what `risk_model` returns for the same inputs to within 0.0001. The page MUST NOT compute the probability itself.

#### Scenario: Agreement with the classifier
- **WHEN** 500 seeded input sets are scored through the route and directly through the classifier
- **THEN** every probability differs by less than 0.0001

#### Scenario: No model call
- **WHEN** inputs are changed 50 times
- **THEN** no language-model call is made and no spend is recorded

### Requirement: A breakdown shows what moved the estimate
Beside the estimate the scenario SHALL show one signed bar for each input, in the direction it moves the estimate, plus the starting point. The bars and the starting point SHALL add up to the model's score for the inputs, so that the estimate can be recomputed from what is shown.

#### Scenario: The bars add up
- **WHEN** the breakdown for any input set is summed with its starting point
- **THEN** the sum equals the model's score for those inputs to within 0.000001

#### Scenario: A not-done lab
- **WHEN** a lab is set to not done
- **THEN** its bar reflects the model's treatment of a missing lab, and the page says the lab is not done and does not show a value for it

### Requirement: The inputs become a note by a fixed template
The inputs SHALL be turned into a message by a fixed template that lists each done lab with its name, abbreviation, value and usual unit, and states each symptom in plain words for its state. The same inputs SHALL always give the same message, and the message MUST contain nothing but the inputs.

#### Scenario: Same inputs, same message
- **WHEN** one input set is turned into a message twice
- **THEN** the two messages are identical

#### Scenario: A not-done lab is left out
- **WHEN** a lab is not done
- **THEN** the message does not mention that lab

### Requirement: The message reads back to the inputs
For any input set, reading the generated message through the text intake and the note reader SHALL give each done lab its value, each not-done lab no value, and each symptom its state, and the probability through that path SHALL equal the estimate to within 0.001.

#### Scenario: All symptom combinations
- **WHEN** each of the 243 symptom combinations is combined with 200 seeded lab settings, including some labs not done, and read back
- **THEN** every symptom reading and every lab value equals its input, and every probability is within 0.001 of the estimate

#### Scenario: The extremes
- **WHEN** every lab is at its lowest, at its highest, and not done
- **THEN** each reads back to its input

### Requirement: The patient can be sent to the assistant
A control SHALL send the generated message to the assistant through the same route and guards as any other message, and the scenario SHALL show the assistant's number beside the dial's. Only this control and the guardrail controls MAY make a language-model call.

#### Scenario: The numbers agree
- **WHEN** the patient is sent and the assistant scores it
- **THEN** the assistant's number and the dial's differ by less than 0.001 and the page shows both

#### Scenario: A decline is shown as one
- **WHEN** the assistant declines a sent message
- **THEN** the page shows the decline reason and the fixed message and no number for the assistant

### Requirement: Guardrail controls act on the current patient
The scenario SHALL offer three guardrail controls: one that adds a fixed hidden instruction to the patient's message, one that adds a fixed treatment question to it, and one that sends a fixed off-topic question alone. Each SHALL send its message through the same route and guards as any other, and the page SHALL show what came back next to what the dial shows.

#### Scenario: An instruction in the note
- **WHEN** the hidden-instruction control is used on any patient and the assistant scores the message
- **THEN** the assistant's number is within 0.001 of the dial's, and the page says the instruction was treated as text

#### Scenario: A treatment question
- **WHEN** the treatment control is used
- **THEN** the page shows a decline with its reason and no number

#### Scenario: Off-topic
- **WHEN** the off-topic control is used
- **THEN** the page shows a decline and no number

### Requirement: Free text is still available, collapsed
The scenario SHALL keep a collapsed free-text box that sends one message as it is through the same route, with no history, as the free-text tab did.

#### Scenario: Collapsed by default
- **WHEN** the scenario is opened
- **THEN** the free-text box is not expanded and no message is sent

### Requirement: Nothing here edits a recorded value or gives advice
The scenario MUST NOT start from, load, change or save any queue case or any recorded value, and MUST NOT store a visitor's inputs beyond the current visit. Its text MUST NOT name a treatment, a dose or a test to order, MUST say the patient is invented and the disease fictional, and MUST NOT use the words "diagnosis of", "you have" or "your risk".

#### Scenario: Queue progress is untouched
- **WHEN** queue progress is saved, the scenario is used, and the queue is reopened
- **THEN** the saved progress is exactly as it was

#### Scenario: The fictional notice
- **WHEN** the scenario's text is read
- **THEN** it states that the patient is invented and the disease is fictional, and contains none of the excluded words or any treatment name
