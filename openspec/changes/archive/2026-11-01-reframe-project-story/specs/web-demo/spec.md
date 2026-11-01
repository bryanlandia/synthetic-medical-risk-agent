## ADDED Requirements

### Requirement: The About tab tells the project's story
The About text SHALL state, in plain words, that the disease is fictional and often overlooked, that caught early it is highly treatable, and that missed it becomes a degenerative neurological disease. It SHALL describe the pathway of screen, confirm and treat, say this project is the first stage, and name both costs of delay: the patient's time to diagnosis and the institution's rework and denials.

#### Scenario: The story sections are present
- **WHEN** the About tab is opened
- **THEN** its text contains the disease course, the three-stage pathway with this project marked as stage one, and a statement of the patient and institution costs of delay, each under a heading

#### Scenario: The story stays fictional
- **WHEN** the story sections of the About text are searched for treatment names, doses, any figure, and dollar or days-saved amounts
- **THEN** none is found

### Requirement: The funder is named and marked fictional
The About text and a footer shown on every tab SHALL state that the project is funded by the Kessler Family Foundation, a fictional foundation, to improve diagnosis and outcomes for Velorin-Kessler Syndrome. The foundation MUST NOT appear in any request, report or workflow text.

#### Scenario: The footer is on every tab
- **WHEN** each tab is opened
- **THEN** the footer names the Kessler Family Foundation and says it is fictional

#### Scenario: The foundation is not in the data path
- **WHEN** a check is run and the request body and the report are searched for the foundation's name
- **THEN** it is not found

### Requirement: The About text is accurate about the system
The About text SHALL describe the baseline as the prompted Haiku model with its measured AUC, SHALL call the chat service an assistant, and SHALL keep the notice that the LLM reviewer is not a clinician and a description of the guards.

#### Scenario: Known leftovers are fixed
- **WHEN** the About text is read
- **THEN** it does not say "prompted frontier models" for the Haiku result, does not call the chat service an agent, and includes the guards paragraph and the reviewer caveat
