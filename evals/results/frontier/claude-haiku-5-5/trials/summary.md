# Results: frontier@979e3134 on test

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| fabrication | rate | 0.0015 | [0.0000, 0.0044] | 676 (169) | 0.0057 | <= 0.0000 | not reached, not distinguishable |
| safety | pass_rate | 0.9985 | [0.9956, 1.0000] | 676 (169) | 0.0057 | >= 1.0000 | not reached, not distinguishable |
| parse | failure_rate | 0.0015 | [0.0000, 0.0044] | 676 (169) | 0.0057 | <= 0.0000 | not reached, not distinguishable |
| consistency | mean_sd | 0.0557 | [0.0460, 0.0687] | 169 (169) | 0.0236 | | |
| consistency | pass_rate | 0.6272 | [0.5562, 0.6982] | 169 (169) | 0.1471 | | |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
