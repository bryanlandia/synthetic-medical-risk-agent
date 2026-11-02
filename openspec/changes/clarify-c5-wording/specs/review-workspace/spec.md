## ADDED Requirements

### Requirement: Criteria are worded so a Yes means the criterion holds
Wherever the page shows the wording of a criterion the preparing clinician attested (the preparer answers, the checklist, the released packet and the copied text), a Yes answer SHALL mean the criterion holds. C5 SHALL be shown as "The last PET-CT or comparable imaging was more than 12 months ago, or there has been none." and MUST NOT be shown with a leading negation. The change is display only: the stored answers, the criterion statuses and the policy are unchanged.

#### Scenario: C5 in the preparer answers
- **WHEN** a case is opened and the preparer answers are read
- **THEN** C5 is shown in the positive wording, and a case whose C5 answer is Yes shows C5 as met in the checklist

#### Scenario: C5 in the checklist and the released packet
- **WHEN** the checklist, a released packet and its copied text are read
- **THEN** each shows the same positive wording for C5 and none contains "No PET-CT"

#### Scenario: Other criteria are untouched
- **WHEN** C1 to C4 and C6 are shown
- **THEN** their wording equals the policy text
