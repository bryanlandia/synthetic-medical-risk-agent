# Proposal

## Why

Criterion C5 reads "No PET-CT or comparable imaging in the last 12 months." The preparer's answer is Yes or No to that statement, so a "No" means the patient *did* have recent imaging and the criterion is unmet. A supervisor reading "C5 No PET-CT ... — No" has to untangle a double negative, in the answers table, the checklist and the released packet.

## What Changes

- The web app shows C5 as a positive statement where a supervisor reads it: **"The last PET-CT or comparable imaging was more than 12 months ago, or there has been none."** A Yes answer now reads as the criterion holding, like C3, C4 and C6.
- One display helper in `web/` supplies the shown text for a criterion; every place that shows a criterion's text uses it (answers table, checklist, released packet, copied text). Only C5 is overridden.
- The meaning of the stored answer, the criterion's status logic and the policy are unchanged.

## Capabilities

### Modified Capabilities
- `review-workspace`: the case view, the released packet and the copied text show C5 in the positive wording.

## Impact

- `web/` only: `lib/copy.ts` (helper), `components/CaseView.tsx`, `components/ReleasedPacket.tsx`, and tests.
- No change to the policy files (`risk_model` policy id and hash stay), the agent, the packet prompt, the summaries, the model, `web/content/pet_ct_policy.json`, the cases file or any frozen eval result. No model spend.
- Out of scope: rewording the policy itself (a policy version change that would touch the packet evals); summary sentences written by the model, which may still say "no PET-CT in the last 12 months"; the fixed-template fallback text and gap messages from the service.
- Eval categories affected: none graded by the harness; web tests cover the wording.
