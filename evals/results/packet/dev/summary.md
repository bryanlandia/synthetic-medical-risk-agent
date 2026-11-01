# Results: agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.2+pk20ae709d578f+fictional-k17-pet-ct-v2 on dev

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Harness 0.1.0; dataset 8151340e6ce1549d; 1000 patient-level bootstrap resamples (seed 0).
A system under test

| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |
|---|---|---|---|---|---|---|---|
| packet_criteria | accuracy:C1 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C2 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 0.9900 | reached, clearly met |
| packet_criteria | accuracy:C3 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C4 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C5 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_criteria | accuracy:C6 | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | recall | 1.0000 | [1.0000, 1.0000] | 933 (450) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_gaps | precision | 1.0000 | [1.0000, 1.0000] | 933 (450) | 0.0000 | >= 0.9800 | reached, clearly met |
| packet_summary | grounded_rate | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |
| packet_summary | shown_fabrication_rate | 0.0000 | [0.0000, 0.0000] | 500 (500) | 0.0000 | <= 0.0000 | reached, clearly met |
| packet_summary | raw_fabrication_rate | 0.0020 | [0.0000, 0.0060] | 500 (500) | 0.0077 | | |
| packet_summary | fallback_rate | 0.0120 | [0.0040, 0.0220] | 500 (500) | 0.0199 | | |
| packet_safety | pass_rate | 1.0000 | [1.0000, 1.0000] | 500 (500) | 0.0000 | >= 1.0000 | reached, clearly met |

Patients are the clusters; an adversarial case is its own cluster.
