## ADDED Requirements

### Requirement: Packet results state how often each status occurs
The harness SHALL report, per criterion, how many patients in the stage have each true status (met, unmet, unknown), so an accuracy figure can be read against the mix it was measured on. The dev stage SHALL contain at least 20 patients whose true C1 status is met, and the run SHALL say so when it does not.

#### Scenario: Status counts are in the summary
- **WHEN** a packet stage is summarised
- **THEN** the summary holds, for each of C1 to C6, a count of met, unmet and unknown that sums to the number of patients

#### Scenario: C1 met is exercised
- **WHEN** the dev stage is scored under policy v2
- **THEN** the C1 count of met is at least 20, otherwise the summary carries a warning that C1 accuracy was measured on too few met cases

### Requirement: A policy version is part of the packet system version
The packet system version SHALL include the policy id, so a change of policy is a new system version with its own dev run, freeze, and one look each at the test and adversarial stages. Results of an earlier policy version SHALL be kept and labelled with their version, never overwritten.

#### Scenario: A new policy needs a new dev run
- **WHEN** the test stage is run for a policy id that has had no dev run and freeze
- **THEN** it is refused, as for any other new system version

#### Scenario: Earlier results are kept
- **WHEN** policy v2 results are written
- **THEN** the v1 summaries, calls and ledger entries are still present and name `fictional-k17-pet-ct-v1`

#### Scenario: The reference follows the policy
- **WHEN** the independent reference judges C1
- **THEN** it uses the lab table's mean plus one standard deviation, and a test fails if that differs from the policy's thresholds
