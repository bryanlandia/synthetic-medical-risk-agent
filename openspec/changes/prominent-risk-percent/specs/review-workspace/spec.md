## ADDED Requirements

### Requirement: The case view shows the estimate as a prominent figure
In a case, the estimated risk SHALL be shown as the same large, labelled figure as in Estimate a risk, at the top of the block headed "Why this patient was flagged (context only)", with the range beneath it and the sentence that it is context only and decides no criterion. The figure SHALL NOT be coloured or worded as a decision, and the queue SHALL still show no probability.

#### Scenario: A case with a report
- **WHEN** a case is opened
- **THEN** the percentage is the largest text in the estimate block, labelled as the estimated risk of Velorin-Kessler syndrome (fictional), and "Context only; it decides no criterion" is still shown

#### Scenario: The queue
- **WHEN** the queue is shown
- **THEN** no row shows a probability
