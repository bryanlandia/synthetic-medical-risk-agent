# Proposal

## Why

Criterion C1 of the fictional PET-CT policy asks for two of three labs above their lab reference range. In the dev split that is met for 2 of 500 patients (and unknown for 10); the reference range sits 1.5 to 2 SD out and the labs separate the true classes only weakly (mean z-score 0.26 to 0.44 in true positives). The packet's headline criterion is therefore almost never "met": the accuracy of 1.0 on C1 says little about the met case, and a demo batch drawn from this data would show almost only unmet packets. Real payer policies state their own numeric thresholds rather than reuse the lab's flag, so the fix is a more realistic policy, not a looser grader.

## What Changes

- Policy v2: C1 becomes "at least 2 of Velorin index above 120 mg/dL, Tarnic acid above 360 umol/L and Dorrin ratio above 1.25". The numbers are one SD above each lab's typical value, chosen by that stated rule before looking at which patients it selects, and stated in the policy as plain numbers (no coefficients). The policy states that the thresholds are fictional and that meeting them is not a finding about any patient.
- The policy id becomes `fictional-k17-pet-ct-v2`. C2 to C6 are unchanged.
- C1 evidence text states the policy threshold next to the value (and still gives the lab's own reference range), so a value inside the lab's range but above the policy threshold reads honestly.
- The evals' independent reference judges C1 against mean plus one SD taken from the lab table, and a test ties the policy's numbers to the lab table. The harness reports the count of each true status per criterion and requires at least 20 C1-met patients in the dev stage.
- A policy version is part of the packet system version: v2 needs its own dev run, freeze, and one test and one adversarial look. The v1 results are kept as history, not overwritten.
- The web app's copy of the policy file is refreshed (a test already ties it to the source).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `scan-readiness`: the policy's C1 wording and the rule for judging C1 and its evidence text.
- `eval-harness`: C1 coverage reporting and the versioning of packet results by policy.

## Impact

- `risk_model/` (policy JSON and loader, `scan.py` C1 and evidence text, tests); `web/content/pet_ct_policy.json`; `evals/` (reference, coverage report, kept v1 results, new v2 results and ledger entries); `evals/README.md`.
- No model files, training or data regeneration, so the model hash is unchanged. The summary prompt is unchanged (its hash is part of the system version either way). The attestation fixtures are keyed by patient id and stay as they are.
- Spend: one Haiku call per packet for dev (500), test (931) and adversarial (181) again, about $0.65, under the service's own stage caps. The test and adversarial looks are new looks for a new system version, recorded in the ledger.
- Unblocks the next change (`supervisor-review-workspace`), whose queue needs C1-met cases.
- Out of scope: any UI redesign, changing C2 to C6 or the attestation fixtures, changing the note reader, tuning thresholds against the labels, a second policy per insurer.
- Eval categories affected: criterion accuracy (C1), gap detection, citation grounding and fabrication (C1 evidence text changes), safety, adversarial.
