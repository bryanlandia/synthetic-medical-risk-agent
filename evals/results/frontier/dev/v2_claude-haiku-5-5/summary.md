# Results: frontier@57d9e02c on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| happy_path | auc | 0.6712 | [0.6174, 0.7249] | 500 (500) | 0.1077 | >= 0.7994 | not reached, clearly not met |
| happy_path | brier | 0.1957 | [0.1789, 0.2125] | 500 (500) | 0.0346 | <= 0.1587 | not reached, clearly not met |
| happy_path | log_loss | 0.5782 | [0.5388, 0.6181] | 500 (500) | 0.0815 | <= 0.4822 | not reached, clearly not met |
| happy_path | ece | 0.0441 | [0.0296, 0.0899] | 500 (500) | 0.0603 | <= 0.0643 | reached, not distinguishable |
| symptom_reading | accuracy | 0.9964 | [0.9936, 0.9988] | 500 (500) | 0.0052 | >= 0.6642 | reached, clearly met |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| data_quality | recall:missing_value | 1.0000 | [1.0000, 1.0000] | 156 (156) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9655 | [0.9138, 1.0000] | 58 (58) | 0.0950 | >= 0.5000 | reached, clearly met |
| data_quality | recall:contradiction | 0.9846 | [0.9538, 1.0000] | 65 (65) | 0.0632 | >= 0.5000 | reached, clearly met |
| data_quality | exact_match | 0.9870 | [0.9697, 1.0000] | 231 (231) | 0.0288 | >= 0.5000 | reached, clearly met |
| borderline | uncertain_rate | 0.4868 | [0.3816, 0.5921] | 76 (76) | 0.2251 | >= 0.5000 | not reached, not distinguishable |
| borderline | false_uncertain_rate | 0.2287 | [0.1794, 0.2825] | 223 (223) | 0.1038 | <= 0.1000 | not reached, clearly not met |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
