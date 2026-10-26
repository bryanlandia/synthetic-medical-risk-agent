# Results: floor@1 on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A reference system

| Category | Metric | Value | 95% interval | n (patients) | MDD |
|---|---|---|---|---|---|
| happy_path | auc | 0.5000 | [0.5000, 0.5000] | 500 (500) | 0.0000 |
| happy_path | brier | 0.2100 | [0.1941, 0.2259] | 500 (500) | 0.0318 |
| happy_path | log_loss | 0.6109 | [0.5771, 0.6446] | 500 (500) | 0.0673 |
| happy_path | ece | 0.0007 | [0.0007, 0.0447] | 500 (500) | 0.0481 |
| symptom_reading | accuracy | 0.3284 | [0.3120, 0.3452] | 500 (500) | 0.0333 |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 |
| data_quality | recall:missing_value | 0.0000 | [0.0000, 0.0000] | 156 (156) | 0.0000 |
| data_quality | recall:unit_mismatch | 0.0000 | [0.0000, 0.0000] | 58 (58) | 0.0000 |
| data_quality | recall:contradiction | 0.0000 | [0.0000, 0.0000] | 65 (65) | 0.0000 |
| data_quality | exact_match | 0.0000 | [0.0000, 0.0000] | 231 (231) | 0.0000 |
| borderline | uncertain_rate | 0.0000 | [0.0000, 0.0000] | 76 (76) | 0.0000 |
| borderline | false_uncertain_rate | 0.0000 | [0.0000, 0.0000] | 223 (223) | 0.0000 |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
