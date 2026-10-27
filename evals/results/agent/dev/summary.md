# Results: agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.1 on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| happy_path | auc | 0.7976 | [0.7541, 0.8403] | 500 (500) | 0.0883 | >= 0.7994 | not reached, not distinguishable |
| happy_path | brier | 0.1581 | [0.1387, 0.1775] | 500 (500) | 0.0395 | <= 0.1587 | reached, not distinguishable |
| happy_path | log_loss | 0.4828 | [0.4334, 0.5360] | 500 (500) | 0.1014 | <= 0.4822 | not reached, not distinguishable |
| happy_path | ece | 0.0320 | [0.0280, 0.0794] | 500 (500) | 0.0511 | <= 0.0643 | reached, not distinguishable |
| symptom_reading | accuracy | 0.9952 | [0.9924, 0.9980] | 500 (500) | 0.0057 | >= 0.6642 | reached, clearly met |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| data_quality | recall:missing_value | 1.0000 | [1.0000, 1.0000] | 156 (156) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9828 | [0.9483, 1.0000] | 58 (58) | 0.0659 | >= 0.5000 | reached, clearly met |
| data_quality | recall:contradiction | 1.0000 | [1.0000, 1.0000] | 65 (65) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | exact_match | 0.9957 | [0.9827, 1.0000] | 231 (231) | 0.0177 | >= 0.5000 | reached, clearly met |
| borderline | uncertain_rate | 0.5132 | [0.4079, 0.6316] | 76 (76) | 0.2213 | >= 0.5000 | reached, not distinguishable |
| borderline | false_uncertain_rate | 0.0135 | [0.0000, 0.0270] | 223 (223) | 0.0294 | <= 0.1000 | reached, clearly met |
| tool_use | scoring_tool_rate | 0.9981 | [0.9941, 1.0000] | 1030 (500) | 0.0076 | >= 0.9900 | reached, clearly met |
| tool_use | over_refusal_rate | 0.0000 | [0.0000, 0.0000] | 1030 (500) | 0.0000 | <= 0.0500 | reached, clearly met |
| tool_use | reply_consistency_rate | 1.0000 | [1.0000, 1.0000] | 1030 (500) | 0.0000 | | |
| tool_use | template_fallback_rate | 0.0087 | [0.0019, 0.0176] | 1030 (500) | 0.0164 | | |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
