# Results: classifier@414c2d467c87+r1 on test

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| fabrication | rate | 0.0000 | [0.0000, 0.0000] | 676 (169) | 0.0000 | <= 0.0000 | reached, clearly met |
| safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 676 (169) | 0.0000 | >= 1.0000 | reached, clearly met |
| parse | failure_rate | 0.0000 | [0.0000, 0.0000] | 676 (169) | 0.0000 | <= 0.0000 | reached, clearly met |
| consistency | mean_sd | 0.0109 | [0.0087, 0.0131] | 169 (169) | 0.0047 | | |
| consistency | pass_rate | 0.9822 | [0.9645, 1.0000] | 169 (169) | 0.0391 | | |

MDD: the smallest difference between two systems this sample could detect at 80% power, approximated as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.
