# Results: frontier@979e3134 on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| happy_path | auc | 0.7523 | [0.7015, 0.8012] | 500 (500) | 0.0998 | >= 0.7994 | not reached, not distinguishable |
| happy_path | brier | 0.1731 | [0.1551, 0.1910] | 500 (500) | 0.0360 | <= 0.1587 | not reached, not distinguishable |
| happy_path | log_loss | 0.5227 | [0.4802, 0.5653] | 500 (500) | 0.0852 | <= 0.4822 | not reached, not distinguishable |
| happy_path | ece | 0.0453 | [0.0328, 0.0918] | 500 (500) | 0.0593 | <= 0.0643 | reached, not distinguishable |
| symptom_reading | accuracy | 0.9976 | [0.9952, 0.9996] | 500 (500) | 0.0045 | >= 0.6642 | reached, clearly met |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| data_quality | recall:missing_value | 1.0000 | [1.0000, 1.0000] | 156 (156) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9138 | [0.8448, 0.9828] | 58 (58) | 0.1420 | >= 0.5000 | reached, clearly met |
| data_quality | recall:contradiction | 1.0000 | [1.0000, 1.0000] | 65 (65) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | exact_match | 0.9784 | [0.9567, 0.9957] | 231 (231) | 0.0384 | >= 0.5000 | reached, clearly met |
| borderline | uncertain_rate | 0.3553 | [0.2500, 0.4605] | 76 (76) | 0.2121 | >= 0.5000 | not reached, clearly not met |
| borderline | false_uncertain_rate | 0.0717 | [0.0404, 0.1076] | 223 (223) | 0.0686 | <= 0.1000 | reached, not distinguishable |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
