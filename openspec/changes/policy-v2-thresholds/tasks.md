## 1. Policy v2 and C1 in `risk_model`

- [x] 1.1 Change the policy file to id `fictional-k17-pet-ct-v2` with per-lab C1 thresholds (120, 360, 1.25), the new C1 wording, and a sentence that the thresholds are fictional and say nothing about any patient; update the markdown copy; verify with policy tests that the wording matches in both files, no coefficient appears, the id is v2, and the three thresholds equal each lab's mean plus one SD in `labs.py`
- [x] 1.2 Judge C1 against the thresholds (strictly above, after unit conversion, impossible values unreported) and write the new evidence text with the threshold and the lab's reference range, without "high" or "low"; verify with updated `test_scan.py` for every C1 scenario in the spec: two labs above, a value above the threshold but inside the lab range, exactly at the threshold, one above and one unreported, cannot be met, alternate unit, impossible value
- [x] 1.3 Check the summary verifier and template summary against the new evidence text; verify with `test_summary.py` that a faithful draft citing a threshold passes, an invented number still fails, and the template passes its own verifier; run `uv run pytest -q` in `risk_model/`

## 2. Service and web copy

- [x] 2.1 Confirm `/healthz` and the agent tests report the v2 policy id; run `uv run pytest -q` in `agent/` and fix any test that pinned v1 text or values
- [x] 2.2 Copy the policy JSON to `web/content/pet_ct_policy.json`; verify the existing Playwright test that ties the copy to the source passes, and run `npm test` and `npm run typecheck` from `web/` (restore `next-env.d.ts` and `tsconfig.json` afterwards)

## 3. Evals reference and coverage

- [x] 3.1 Move C1 in the independent reference to mean plus one SD from `data_gen.labs`; verify with `test_packet_eval.py` that it equals the policy's thresholds, and update the hand-built reference cases (including a value inside the lab range but above the threshold, and exactly at it)
- [x] 3.2 Add the dev-stage warning when true C1-met is under 20 and keep the per-criterion status counts in the summary; verify with a test on a hand-built set under and over 20, then run `uv run pytest -q` and `uv run evals regression` from `evals/`

## 4. Keep v1, score v2

- [x] 4.1 Move `evals/results/packet/` to `evals/results/packet_v1/` and add a note at the top of its report that it was scored under policy v1; verify the v1 ledger entries are untouched and the v1 summaries still name `fictional-k17-pet-ct-v1`
- [x] 4.2 Run `uv run evals packet estimate`, then the live dev stage (`packet run --split dev --live --yes`); verify C1 met is at least 20 in the status counts, record any missed target and read its failing transcripts before the freeze
- [x] 4.3 Run `packet freeze`, then `packet run --split test --live --yes --final` and `--split adversarial --live --yes --final` once each; verify the ledger holds one `packet` entry per stage for the v2 system version and the v1 entries remain
- [x] 4.4 Write the v2 `report.md` and `reading.md` (what was read for each missed target, the status mix, how C1 now compares with v1); verify it lists every target with its label and carries the synthetic-data notice

## 5. Docs

- [x] 5.1 Update `evals/README.md`, `agent/README.md` and the About text for the v2 C1 wording and the kept v1 results; run `uv run evals regression` and `npm test`, and confirm the model hash is unchanged

## Workflow follow-up

- Do not retrain or regenerate data for this change.
- Archive the change after the PR is merged.
