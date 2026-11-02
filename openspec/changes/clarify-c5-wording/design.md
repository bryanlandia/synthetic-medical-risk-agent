# Design

## Context

The criterion text comes from two sources: the policy copy `web/content/pet_ct_policy.json` (used for the preparer answers table via `WORDING` in `CaseView.tsx`) and the packet response's `criteria[].text` (checklist in `CaseView.tsx`, released packet table and copy text in `ReleasedPacket.tsx`). Both carry the policy's C5 text, "No PET-CT or comparable imaging in the last 12 months." A Yes attests the criterion holds, so "No" reads as imaging having happened.

## Goals / Non-Goals

**Goals:** remove the double negative everywhere a supervisor reads a criterion; keep the change small and reversible.

**Non-Goals:** changing the policy text, id or hash; re-running or re-recording any eval; changing model-written summaries or service gap messages.

## Decisions

- **Display override in `web/lib/copy.ts`, not a policy change.** A `criterionText(id, text)` helper returns the positive wording for C5 and the given text otherwise; the four places call it. Alternative: reword C5 in the policy (clearer at the source, but it changes the policy text and hash, the policy id convention (a v3), the web policy copy, and the packet evals' recorded prompts, so it is a separate, larger change if wanted).
- **Positive wording keeps the meaning.** "The last PET-CT or comparable imaging was more than 12 months ago, or there has been none" is true exactly when "no PET-CT or comparable imaging in the last 12 months" is, so stored answers and statuses stay valid. Assumption: "comparable imaging" keeps the policy's own phrase.
- **A test pins the override to the policy.** A test fails if C5 disappears from the policy copy or its id changes, so the override cannot silently attach to the wrong criterion, and checks that C1 to C4 and C6 are shown unchanged.

## Risks / Trade-offs

- [The shown C5 text differs from the policy file's] → the override is one helper with a test and a comment; the About text is unaffected as it does not quote C5.
- [Model-written summaries may still use the old phrasing] → out of scope and listed in the proposal; the summary is not a criterion label.
