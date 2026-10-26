# Results: lab_only@1 on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A reference system

| Category | Metric | Value | 95% interval | n (patients) | MDD |
|---|---|---|---|---|---|
| happy_path | auc | 0.7814 | [0.7339, 0.8253] | 500 (500) | 0.0893 |
| happy_path | brier | 0.1647 | [0.1454, 0.1836] | 500 (500) | 0.0383 |
| happy_path | log_loss | 0.5003 | [0.4515, 0.5482] | 500 (500) | 0.0978 |
| happy_path | ece | 0.0275 | [0.0256, 0.0747] | 500 (500) | 0.0488 |
| symptom_reading | accuracy | 0.3284 | [0.3120, 0.3452] | 500 (500) | 0.0333 |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 |
| data_quality | recall:missing_value | 0.0000 | [0.0000, 0.0000] | 156 (156) | 0.0000 |
| data_quality | recall:unit_mismatch | 0.0000 | [0.0000, 0.0000] | 58 (58) | 0.0000 |
| data_quality | recall:contradiction | 0.0000 | [0.0000, 0.0000] | 65 (65) | 0.0000 |
| data_quality | exact_match | 0.0000 | [0.0000, 0.0000] | 231 (231) | 0.0000 |
| borderline | uncertain_rate | 0.4737 | [0.3684, 0.5921] | 76 (76) | 0.2276 |
| borderline | false_uncertain_rate | 0.0135 | [0.0000, 0.0270] | 223 (223) | 0.0294 |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
