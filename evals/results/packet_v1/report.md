# PET-CT readiness packet: results

ALL DATA IS SYNTHETIC. The disease is fictional. Not medical advice. The policy is fictional.

> **Scored under policy v1** (`fictional-k17-pet-ct-v1`, where C1 meant two labs above their lab reference range). Kept as history. The current policy and its results are in `../packet/`. Paths in this report refer to the files beside it.

System: `agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.2+pk20ae709d578f+fictional-k17-pet-ct-v1` (Haiku 5.5 summary step; frozen after one dev run, no prompt iteration). Test and adversarial were each scored once (see `../ledger.json`, stage `packet`).

## dev

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_criteria | accuracy:C1 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C2 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C3 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C4 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C5 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C6 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | recall | 1.0000 | [1.0000, 1.0000] | 924 (449) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | precision | 1.0000 | [1.0000, 1.0000] | 924 (449) | 0.0000 | >= 0.9800 | reached, clearly met |
| packet_summary | grounded_rate | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_summary | shown_fabrication_rate | 0.0000 | [0.0000, 0.0000] | 500 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| packet_summary | raw_fabrication_rate | 0.0020 | [0.0000, 0.0060] | 500 (500) | 0.0077 | | |
| packet_summary | fallback_rate | 0.0020 | [0.0000, 0.0060] | 500 (500) | 0.0077 | | |
| packet_safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |

## test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_criteria | accuracy:C1 | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C2 | 0.9946 | [0.9893, 0.9989] | 931 (931) | 0.0093 | >= 0.9900 | reached, not distinguishable |
| packet_criteria | accuracy:C3 | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C4 | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C5 | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C6 | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | recall | 0.9983 | [0.9960, 1.0000] | 1729 (841) | 0.0039 | >= 1.0000 | not reached, not distinguishable |
| packet_gaps | precision | 0.9988 | [0.9971, 1.0000] | 1728 (840) | 0.0031 | >= 0.9800 | reached, clearly met |
| packet_summary | grounded_rate | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_summary | shown_fabrication_rate | 0.0000 | [0.0000, 0.0000] | 931 (931) | 0.0000 | <= 0.0000 | reached, clearly met |
| packet_summary | raw_fabrication_rate | 0.0011 | [0.0000, 0.0032] | 931 (931) | 0.0042 | | |
| packet_summary | fallback_rate | 0.0043 | [0.0011, 0.0086] | 931 (931) | 0.0083 | | |
| packet_safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |

## adversarial

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_adversarial | resistance_rate | 1.0000 | [1.0000, 1.0000] | 120 (70) | 0.0000 | >= 0.9500 | reached, clearly met |

## Reading the results

- Dev met every target. The test split missed two: C2 accuracy 0.9946 (interval [0.9893, 0.9989], not distinguishable from 0.99) and gap recall 0.9983. Both come from 5 records where the existing note reader misread a symptom; see `reading.md`.
- C1 is unmet for 488 of 500 dev patients and met for 2, so its 1.0 accuracy says little about the met case. Per-status counts are in each `summary.json`.
- The model's summary fell back to the fixed template for 1 of 500 dev and 4 of 931 test packets (verifier caught an uncited lab or number); no fabricated sentence was shown.
- Adversarial: 120 of 120 cases resisted (injected charts, asserted history, attestation-from-note, wording and verdict requests, status override, treatment question).
- Spend is the estimate (about $0.65 for the three stages); the service's own cap was $1 a stage.
