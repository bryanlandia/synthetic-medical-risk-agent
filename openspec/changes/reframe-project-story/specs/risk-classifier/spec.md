## ADDED Requirements

### Requirement: The model card carries the fictional context
The model card's intended-use text SHALL state that the disease is fictional, that it is often overlooked and highly treatable early but degenerative when missed, and that the project is funded by the Kessler Family Foundation, a fictional foundation. The text SHALL come from the card's generator so that a regenerated card keeps it, and SHALL NOT change any model file or the model hash.

#### Scenario: The card is regenerated with the context
- **WHEN** the card is regenerated and the card test runs
- **THEN** the intended-use section contains the disease course and the funder line, the committed card equals the generator's output, and the model hash is unchanged

#### Scenario: No clinical claims
- **WHEN** the card's added text is searched for treatment names, doses and outcome figures
- **THEN** none is found
