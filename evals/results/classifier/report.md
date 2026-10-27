# Classifier: final results

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

- System `classifier@414c2d467c87+r1`; model hash `414c2d467c87d44bbf3cd8d92454a4041a133f9bc2403b11a521e59ee8191443`. Each protected split was scored once with `--final` (the ledger records it).
- The model was fitted on train without the dev ids; the regularisation and the conflict rule were chosen on dev.
- Targets are targets v1; 'reached' is the plain fact and the label says whether the 95% interval settles it.

- Determinism: 676 of 676 matched-pair records gave the identical report in all three trials. (The consistency metrics below are a different thing: the spread of one patient's probability across the four documentation settings, whose notes differ.)

## test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| happy_path | auc | 0.7955 | [0.7620, 0.8274] | 931 (931) | 0.0668 | >= 0.7994 | not reached, not distinguishable |
| happy_path | brier | 0.1553 | [0.1429, 0.1688] | 931 (931) | 0.0266 | <= 0.1587 | reached, not distinguishable |
| happy_path | log_loss | 0.4827 | [0.4486, 0.5202] | 931 (931) | 0.0728 | <= 0.4822 | not reached, not distinguishable |
| happy_path | ece | 0.0422 | [0.0292, 0.0690] | 931 (931) | 0.0397 | <= 0.0643 | reached, not distinguishable |
| symptom_reading | accuracy | 0.9940 | [0.9916, 0.9963] | 931 (931) | 0.0047 | >= 0.6642 | reached, clearly met |
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 3634 (931) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 3634 (931) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 3634 (931) | 0.0000 | <= 0.0000 | reached, clearly met |
| data_quality | recall:missing_value | 1.0000 | [1.0000, 1.0000] | 466 (313) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:unit_mismatch | 1.0000 | [1.0000, 1.0000] | 155 (150) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:contradiction | 1.0000 | [1.0000, 1.0000] | 203 (203) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | exact_match | 1.0000 | [1.0000, 1.0000] | 690 (512) | 0.0000 | >= 0.5000 | reached, clearly met |
| borderline | uncertain_rate | 0.5838 | [0.4835, 0.6813] | 197 (131) | 0.2024 | >= 0.5000 | reached, not distinguishable |
| borderline | false_uncertain_rate | 0.0047 | [0.0000, 0.0123] | 633 (393) | 0.0134 | <= 0.1000 | reached, clearly met |
| consistency | mean_sd | 0.0109 | [0.0087, 0.0131] | 169 (169) | 0.0047 | | |
| consistency | pass_rate | 0.9822 | [0.9645, 1.0000] | 169 (169) | 0.0391 | | |

## adversarial

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 598 (403) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 598 (403) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 598 (403) | 0.0000 | <= 0.0000 | reached, clearly met |
| data_quality | recall:missing_value | 1.0000 | [1.0000, 1.0000] | 58 (58) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9818 | [0.9455, 1.0000] | 55 (55) | 0.0700 | >= 0.5000 | reached, clearly met |
| data_quality | recall:impossible_value | 1.0000 | [1.0000, 1.0000] | 60 (60) | 0.0000 | | |
| data_quality | recall:contradiction | 1.0000 | [1.0000, 1.0000] | 55 (55) | 0.0000 | >= 0.5000 | reached, clearly met |
| data_quality | recall:note_flag_disagreement | 0.0175 | [0.0000, 0.0526] | 57 (57) | 0.0698 | | |
| data_quality | exact_match | 0.8000 | [0.7509, 0.8456] | 285 (285) | 0.0983 | >= 0.5000 | reached, clearly met |
| borderline | uncertain_rate | 0.6091 | [0.5180, 0.7000] | 110 (110) | 0.1829 | >= 0.5000 | reached, clearly met |
| borderline | false_uncertain_rate | 0.0140 | [0.0000, 0.0350] | 143 (143) | 0.0397 | <= 0.1000 | reached, clearly met |
| adversarial | resistance_rate | 1.0000 | [1.0000, 1.0000] | 60 (60) | 0.0000 | | |

## trials

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 676 (169) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 676 (169) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 676 (169) | 0.0000 | <= 0.0000 | reached, clearly met |
| consistency | mean_sd | 0.0109 | [0.0087, 0.0131] | 169 (169) | 0.0047 | | |
| consistency | pass_rate | 0.9822 | [0.9645, 1.0000] | 169 (169) | 0.0391 | | |

## Compared with the frontier baseline (test)

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0. Systems: classifier `classifier@414c2d467c87+r1`, frontier `frontier@979e3134`. Same patients, one record each: 931 patients (0 only in classifier's run, 0 only in frontier's, left out).

### Paired differences (A minus B, 95% interval from a patient-clustered bootstrap)

| Metric | classifier | frontier | Difference | 95% interval | MDD | Verdict |
|---|---|---|---|---|---|---|
| auc (higher is better) | 0.7955 | 0.7350 | +0.0605 | [+0.0368, +0.0841] | 0.0343 | classifier is better |
| brier (lower is better) | 0.1553 | 0.1810 | -0.0257 | [-0.0340, -0.0180] | 0.0118 | classifier is better |
| log_loss (lower is better) | 0.4827 | 0.5404 | -0.0577 | [-0.0800, -0.0369] | 0.0310 | classifier is better |

MDD: the smallest difference this sample could detect at 80% power. A verdict says better or worse only when the whole interval is on one side of zero.

### Every other metric, side by side (not paired)

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

## Failing transcripts read

### happy_path (20 transcripts read)

319 of the 1,438 test happy-path trials (22%) are on the wrong side of 0.5. Twenty read. In 11 of them the reported probability is within 0.07 of the record's true probability and the label was drawn against it (true probabilities of 0.03 to 0.48 for positives); this is the label noise no system can classify. Across all 319 the true probability has a median of 0.36 and half lie between 0.3 and 0.7, and the median distance from the true probability is 0.065 (0.033 for the passing). Nine of the 20 differ from the true probability by more than 0.07 and six by more than 0.15: three of those six have missing labs (the model sits a missing lab at the typical value), one has a contradiction warning, and two (a true 0.40 reported as 0.57, a true 0.18 reported as 0.37) show no data problem and look like weighting error on single records. Missing labs are only slightly more common among all failing trials (36%) than passing ones (31%). The evidence in every transcript is consistent with the report; no invented value, unsafe text or invalid report appears. Not a grader fault. The AUC and log-loss targets are missed by 0.004 and 0.0005 with intervals that contain the target, so they are not distinguishable from met.

