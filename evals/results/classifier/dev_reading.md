# Reading the classifier's failing dev transcripts

ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.

Model `classifier@414c2d467c87+r1`, dev split (500 patients), `evals run --system classifier --split dev`. Twenty failing
happy-path and twenty failing borderline transcripts were read (`training/` `readfail`-style sample, seed 3), and the whole
failing sets were then counted so the reading is not only an impression.

Fabrication, safety and parse: 0 failures in 1,030 reports each. No transcript needed reading for them.

## Happy path (114 of 500 patients are on the wrong side of 0.5)

- In 13 of the 20 read, the reported probability is within 0.07 of the record's true probability, and the true probability
  itself is between 0.09 and 0.70. The label was drawn the other way. This is the irreducible noise of a probabilistic
  label: the oracle's AUC is 0.817 and no system can classify these patients correctly. Four more differ by 0.08 to 0.12.
- Across all 114 failing patients the median distance from the true probability is 0.059 (0.033 for the passing ones), and
  a missing lab is no more common among them (33% against 31%). Missing labs do not explain these failures.
- Three of the 20 read had a gap of more than 0.15 (a true 0.18 reported as 0.41 with a Velorin index of 141; a true 0.51
  reported as 0.32 with tremor read as possible; a true 0.47 reported as 0.15 with a lab missing). Share of all failing
  patients with such a gap: 18% (7% of the passing).

## Borderline (40 of 299 patients fail)

- These are records whose true probability is in the 0.4 to 0.6 band that were reported outside it, or clear records
  reported as uncertain. The median distance from the true probability is 0.181 (0.027 for the passing ones); 62% differ by
  more than 0.15 (3% of the passing).
- A missing lab is the main cause: 58% of the failing patients have one against 28% of the passing ones. With a lab missing
  the classifier sits that lab at the typical value with its indicator on, and cannot know where the real value was. In the
  20 transcripts read (17 different patients, three of them in two suites), 10 patients had one or more missing labs and 2
  had a contradiction warning (a stale note value that the classifier does not use).
- The remaining failures are small gaps (a reported 0.35 for a true 0.47). Probabilities are calibrated, not widened, so
  they land just outside the band.

## What this does not show

- No transcript shows an invented value, unsafe text or an invalid report.
- No grader fault was found: in every read transcript the grader's verdict follows from the report and the record.
- The borderline target (uncertain rate of at least 0.5) is reached at 0.513, not distinguishable from the target.
