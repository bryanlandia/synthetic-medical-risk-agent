# Design

## Context

See proposal.md for motivation. Policy v1 is `risk_model/src/risk_model/policy/pet_ct_k17.json` (`c1_labs`, `c1_min`, wording per criterion). `scan.py` judges C1 in `_c1`, which counts labs whose `_lab_evidence` state is `high` (value above `lab.ref_hi`), and writes evidence text like "Velorin index 142 mg/dL (high; reference 70 to 130 mg/dL)". The web app holds a copy of the policy file (`web/content/pet_ct_policy.json`) that a Playwright test compares with the source. The evals' independent reference is `packet_eval.c1_status`, which also uses `ref_hi`. The packet system version is `agent@...+pk<prompt hash>+<policy id>`, and protected stages are gated on a dev run and a freeze for exactly that version (`packet_cli`). A dev-split analysis (read-only, 500 patients) showed the count of patients with 2 or more of the three labs above a threshold: 2 above `ref_hi`, 33 above mean + 1 SD, 110 above mean + 0.5 SD.

## Goals / Non-Goals

**Goals:** make C1 "met" common enough that a batch of packets shows the met path, with a rule that is principled and stated in the policy; keep every guarantee about citations, gaps and unit handling; re-measure honestly under a new system version.

**Non-Goals:** UI changes; changing C2 to C6, the attestation fixtures, the note reader, the summary prompt or the model; choosing thresholds to separate the true classes; one policy per insurer.

## Decisions

- **Thresholds are one SD above the typical value, stated as numbers.** 120 mg/dL, 360 umol/L and 1.25 (ratio) are `mean + sd` from the lab table. The rule was fixed before looking at which patients it selects; the alternatives (0.5 SD gives 110 met in dev, 1 SD gives 33) were compared only on how many met cases a demo needs (about 8 to 10 of 30), and 1 SD is the plainer "clearly elevated" rule. The label-split table in the exploration is background for why no lab-only rule can track the disease well; it is not a selection criterion. Alternative: keep `ref_hi`, which leaves C1 met for 0.4%.
- **The policy holds numbers, not a formula.** A policy states thresholds; computing them at run time from the lab table would hide a policy decision inside code. A `risk_model` test asserts the three numbers equal `mean + sd` in `labs.py`, so the two cannot drift apart silently. Strictly greater than: a value at the threshold does not count.
- **The lab's reference range stops deciding C1 but stays in the evidence.** Evidence reads "Velorin index 125 mg/dL (above the policy threshold of 120 mg/dL; lab reference range 70 to 130 mg/dL)". The words "high" and "low" go, because they belong to the lab's flag and would contradict the policy threshold. The summary verifier already allows numbers from cited evidence and from the criterion's own wording, so the thresholds in C1's wording and the evidence need no verifier change.
- **The unknown and unmet logic is unchanged,** with "above threshold" replacing "high" (`unreported` still means not on the chart, or impossible).
- **The evals' reference stays independent.** `packet_eval` computes `mean + sd` from `data_gen.labs`, not from the policy file, and a test asserts it equals the policy's numbers. If the policy and the lab table disagree, the reference test fails rather than the grader quietly following the service.
- **Coverage reporting.** The packet run already writes `status_counts`; the dev run adds a warning in the summary when true C1-met is under 20. Expected: about 33.
- **Versioning and history.** The policy id is already part of the system version, so v2 needs a new dev run, freeze and one look each at test and adversarial. Before the v2 dev run, the v1 results directory is moved to `evals/results/packet_v1/` (including `report.md` and `reading.md`), the v1 ledger entries stay, and the new `results/packet/` carries v2. The v1 report gets a one-line note that it was scored under policy v1.
- **Reproducibility and cost.** No new randomness; the fixtures are unchanged. Pinned prompt and model are as before. Spend is about $0.65 for three stages, each capped at $1 by the service.
- **Risk that the flag and the criterion confuse a reader.** The chart's H/L flag (lab range) and C1 (policy threshold) now differ by design. The evidence text states both, and the next change's UI will show them side by side.

## Risks / Trade-offs

- [New looks at test and adversarial] → deliberate: it is a new system version; the ledger records them and the v1 numbers remain. The reading of dev misses is recorded before the freeze, as before.
- [Thresholds inside the reference range look odd] → they are payer-style cutoffs, stated in the policy as fictional, with a sentence that meeting them says nothing about any patient.
- [A met C1 count under 20 in dev] → measured at about 33; if the run shows fewer the summary says so, and the next change must pick its batch from what exists.
- [C2 errors from the note reader stay] → unchanged by this change and recorded in the v1 reading; C2 accuracy is expected to be about the same.
