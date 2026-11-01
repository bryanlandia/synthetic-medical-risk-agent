# Proposal

## Why

The demo reads as a diagnosis toy: a risk score for an invented disease. The story that makes it worth building is a provider-side one. Velorin-Kessler Syndrome is often overlooked; caught early it is highly treatable, and missed it becomes a degenerative neurological disease. Delays in getting a confirmatory scan authorized cost the patient time and cost the institution staff hours and unreimbursed work. The text and framing should say this before the features that follow (`evidence-first-chart`, `pet-ct-readiness`) arrive.

## What Changes

- Rewrite `web/content/about.md`: the disease course (fictional), the pathway (screen, confirm, treat) and the two ledgers (patient time to diagnosis, institution rework and denials); this project as stage one; an updated list of what is next.
- State that the project is funded by the fictional Kessler Family Foundation to improve diagnosis and outcomes, in the About text and the page footer. The foundation stays out of the workflow itself.
- Carry the disease course and funder line into the model card by editing the card template in `training/` (the card is generated; `web/content/model-card.md` is refreshed by `training card`), and into the READMEs.
- Fix the known About leftovers: "prompted frontier models" should read prompted Haiku (AUC 0.735); remaining "agent" wording; restore the guards paragraph and the "LLM reviewer is not a clinician" caveat.
- Keep every claim fictional and non-clinical: no real treatment names, no outcome numbers, no savings figures.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-demo`: the About tab and a footer on every tab carry the funder line and the disease story; the existing fictional-disease and no-integration requirements still hold.
- `risk-classifier`: the model card's intended-use text carries the same fictional context, from the card generator.

## Impact

- `web/content/about.md`, `web/` footer component, `training/` model-card template and the regenerated `web/content/model-card.md`, READMEs.
- The model card text changes but not the model files, so the model hash is unchanged. Tests that fail on a stale card must be regenerated, not edited by hand.
- Out of scope: any scoring, UI feature or eval change; real clinical claims; dollar or days-saved figures.
- Eval categories affected: none. Web Playwright tests on About headings and the fictional title are updated.
