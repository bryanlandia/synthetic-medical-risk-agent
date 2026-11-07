## ADDED Requirements

### Requirement: The estimated risk is the most prominent element of a result
Wherever the page shows a risk estimate (the Estimate a risk panel and the free-text report card), the percentage SHALL be shown as a figure at least 3.5rem high, in the theme's dark teal rather than a red, amber or green, with a label above it that names Velorin-Kessler syndrome and says it is fictional, and with its range or uncertain band directly beneath. It SHALL be the largest text in the result, and it MUST NOT use a verdict word.

#### Scenario: The Estimate panel
- **WHEN** Estimate a risk is opened
- **THEN** the percentage is at least 3.5rem, the largest text in the Estimate block, and labelled as the estimated risk of the fictional syndrome

#### Scenario: The free-text card
- **WHEN** a message is scored in the free-text box
- **THEN** the card shows the percentage in the same figure, with the uncertain badge beneath it, and a decline shows no figure
