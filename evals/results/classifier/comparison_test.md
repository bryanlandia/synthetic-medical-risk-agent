# classifier compared with frontier on test

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0. Systems: classifier `classifier@414c2d467c87+r1`, frontier `frontier@979e3134`. Same patients, one record each: 931 patients (0 only in classifier's run, 0 only in frontier's, left out).

## Paired differences (A minus B, 95% interval from a patient-clustered bootstrap)

| Metric | classifier | frontier | Difference | 95% interval | MDD | Verdict |
|---|---|---|---|---|---|---|
| auc (higher is better) | 0.7955 | 0.7350 | +0.0605 | [+0.0368, +0.0841] | 0.0343 | classifier is better |
| brier (lower is better) | 0.1553 | 0.1810 | -0.0257 | [-0.0340, -0.0180] | 0.0118 | classifier is better |
| log_loss (lower is better) | 0.4827 | 0.5404 | -0.0577 | [-0.0800, -0.0369] | 0.0310 | classifier is better |

MDD: the smallest difference this sample could detect at 80% power. A verdict says better or worse only when the whole interval is on one side of zero.

## Every other metric, side by side (not paired)

| Category | Metric | classifier | frontier |
|---|---|---|---|
| happy_path | auc | 0.7955 [0.7620, 0.8274] | 0.7350 [0.6996, 0.7679] |
| happy_path | brier | 0.1553 [0.1429, 0.1688] | 0.1810 [0.1687, 0.1938] |
| happy_path | log_loss | 0.4827 [0.4486, 0.5202] | 0.5404 [0.5114, 0.5707] |
| happy_path | ece | 0.0422 [0.0292, 0.0690] | 0.0594 [0.0445, 0.0903] |
| symptom_reading | accuracy | 0.9940 [0.9916, 0.9963] | 0.9959 [0.9940, 0.9976] |
| fabrication | rate | 0.0000 [0.0000, 0.0000] | 0.0011 [0.0000, 0.0033] |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | 0.9989 [0.9967, 1.0000] |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | 0.0011 [0.0000, 0.0033] |
| data_quality | recall:missing_value | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| data_quality | recall:unit_mismatch | 1.0000 [1.0000, 1.0000] | 0.8903 [0.8377, 0.9355] |
| data_quality | recall:contradiction | 1.0000 [1.0000, 1.0000] | 0.9951 [0.9852, 1.0000] |
| data_quality | exact_match | 1.0000 [1.0000, 1.0000] | 0.9652 [0.9494, 0.9789] |
| borderline | uncertain_rate | 0.5838 [0.4835, 0.6813] | 0.4721 [0.3927, 0.5602] |
| borderline | false_uncertain_rate | 0.0047 [0.0000, 0.0123] | 0.0790 [0.0528, 0.1070] |
| consistency | mean_sd | 0.0109 [0.0087, 0.0131] | 0.0557 [0.0460, 0.0687] |
| consistency | pass_rate | 0.9822 [0.9645, 1.0000] | 0.6272 [0.5562, 0.6982] |

