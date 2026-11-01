## ADDED Requirements

### Requirement: The new report fields pass through and replies may quote them
The service SHALL return the report's `interval` and `gaps` unchanged. The reply check SHALL accept a percentage in a reply that equals the probability, a band edge, an interval bound or a gap bound, and SHALL still reject any other number. The fixed template reply SHALL state the range in one sentence.

#### Scenario: A reply quotes the range
- **WHEN** a model reply quotes the interval's bounds as percentages
- **THEN** the reply check releases it

#### Scenario: An invented number is still rejected
- **WHEN** a model reply quotes a percentage that is none of the probability, a band edge, an interval bound or a gap bound
- **THEN** the reply is replaced by the template reply

#### Scenario: Guards unchanged
- **WHEN** the guard test set runs
- **THEN** every decline, injection and scope test passes as before
