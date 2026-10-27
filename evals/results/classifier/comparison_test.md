# agent compared with classifier on test

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0. Systems: agent `agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.1`, classifier `classifier@414c2d467c87+r1`. Same patients, one record each: 931 patients (0 only in agent's run, 0 only in classifier's, left out).

## Paired differences (A minus B, 95% interval from a patient-clustered bootstrap)

| Metric | agent | classifier | Difference | 95% interval | MDD | Verdict |
|---|---|---|---|---|---|---|
| auc (higher is better) | 0.7955 | 0.7955 | +0.0000 | [+0.0000, +0.0000] | 0.0000 | not distinguishable |
| brier (lower is better) | 0.1553 | 0.1553 | +0.0000 | [+0.0000, +0.0000] | 0.0000 | not distinguishable |
| log_loss (lower is better) | 0.4827 | 0.4827 | +0.0000 | [+0.0000, +0.0000] | 0.0000 | not distinguishable |

MDD: the smallest difference this sample could detect at 80% power. A verdict says better or worse only when the whole interval is on one side of zero.

## Every other metric, side by side (not paired)

| Category | Metric | agent | classifier |
|---|---|---|---|
| happy_path | auc | 0.7955 [0.7620, 0.8274] | 0.7955 [0.7620, 0.8274] |
| happy_path | brier | 0.1553 [0.1429, 0.1688] | 0.1553 [0.1429, 0.1688] |
| happy_path | log_loss | 0.4827 [0.4486, 0.5202] | 0.4827 [0.4486, 0.5202] |
| happy_path | ece | 0.0422 [0.0292, 0.0690] | 0.0422 [0.0292, 0.0690] |
| symptom_reading | accuracy | 0.9940 [0.9916, 0.9963] | 0.9940 [0.9916, 0.9963] |
| fabrication | rate | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| data_quality | recall:missing_value | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| data_quality | recall:unit_mismatch | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| data_quality | recall:contradiction | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| data_quality | exact_match | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| borderline | uncertain_rate | 0.5838 [0.4835, 0.6813] | 0.5838 [0.4835, 0.6813] |
| borderline | false_uncertain_rate | 0.0047 [0.0000, 0.0123] | 0.0047 [0.0000, 0.0123] |
| consistency | mean_sd | 0.0109 [0.0087, 0.0131] | 0.0109 [0.0087, 0.0131] |
| consistency | pass_rate | 0.9822 [0.9645, 1.0000] | 0.9822 [0.9645, 1.0000] |

