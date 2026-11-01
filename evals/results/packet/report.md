# PET-CT readiness packet: results (policy v2)

ALL DATA IS SYNTHETIC. The disease is fictional. Not medical advice. The policy is fictional.

Scored under policy `fictional-k17-pet-ct-v2`: C1 asks for at least 2 of Velorin index above 120 mg/dL, Tarnic acid above 360 umol/L and Dorrin ratio above 1.25 (one SD above typical). The policy-v1 results (C1 against the lab reference range) are kept in `../packet_v1/`.

System: `agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.2+pk20ae709d578f+fictional-k17-pet-ct-v2` (Haiku 5.5 summary step; the summary prompt is unchanged from v1 and was frozen after one dev run). Test and adversarial were each scored once for this version (see `../ledger.json`, stage `packet`).

## dev

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_criteria | accuracy:C1 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C2 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C3 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C4 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C5 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C6 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | recall | 1.0000 | [1.0000, 1.0000] | 933 (450) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | precision | 1.0000 | [1.0000, 1.0000] | 933 (450) | 0.0000 | >= 0.9800 | reached, clearly met |
| packet_summary | grounded_rate | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_summary | shown_fabrication_rate | 0.0000 | [0.0000, 0.0000] | 500 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| packet_summary | raw_fabrication_rate | 0.0020 | [0.0000, 0.0060] | 500 (500) | 0.0077 | | |
| packet_summary | fallback_rate | 0.0120 | [0.0040, 0.0220] | 500 (500) | 0.0199 | | |
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
| packet_gaps | recall | 0.9983 | [0.9960, 1.0000] | 1746 (845) | 0.0039 | >= 1.0000 | not reached, not distinguishable |
| packet_gaps | precision | 0.9989 | [0.9971, 1.0000] | 1745 (844) | 0.0032 | >= 0.9800 | reached, clearly met |
| packet_summary | grounded_rate | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_summary | shown_fabrication_rate | 0.0000 | [0.0000, 0.0000] | 931 (931) | 0.0000 | <= 0.0000 | reached, clearly met |
| packet_summary | raw_fabrication_rate | 0.0054 | [0.0011, 0.0107] | 931 (931) | 0.0094 | | |
| packet_summary | fallback_rate | 0.0193 | [0.0107, 0.0290] | 931 (931) | 0.0179 | | |
| packet_safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 931 (931) | 0.0000 | >= 1.0000 | reached, clearly met |

## adversarial

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_adversarial | resistance_rate | 1.0000 | [1.0000, 1.0000] | 120 (70) | 0.0000 | >= 0.9500 | reached, clearly met |

## Reading the results

- C1 now has cases to measure: met for 33 of 500 dev and 54 of 931 test patients (v1: 2 of 500 on dev). Accuracy on C1 is 1.0 on both.
- The test split missed the same two targets as v1: C2 accuracy 0.9946 (interval [0.9893, 0.9989]) and gap recall 0.9983. Both come from the same 5 records where the existing note reader misread a symptom; see `reading.md`.
- Template fallbacks rose to 6 of 500 dev and 18 of 931 test packets (v1: 1 and 4). The verifier caught each; no fabricated sentence was shown. The cause was not read (see `reading.md`).
- Adversarial: 120 of 120 cases resisted.
- Spend was the estimate, about $0.65 for the three stages; the service's own cap was $1 a stage.
