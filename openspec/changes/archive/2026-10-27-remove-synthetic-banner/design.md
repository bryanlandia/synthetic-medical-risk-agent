# Design

## Context

The banner was a header in `Demo.tsx`, later moved into a footer fixed to the bottom of the screen. It said the data is synthetic, the disease is fictional and the output is not medical advice, and it carried the "MOCK EHR" label. The owner wants it gone. The page keeps a subtitle under the title; the code change uses it to carry the fictional status.

## Decisions

**1. The fictional status stays on every screen through the title.** The title now reads "Decision support for Velorin-Kessler Syndrome diagnosis (fictional disease)". The requirement is narrowed to that, so the spec says what the page does and a test can check it.

**2. "Synthetic data" and "not medical advice" are no longer required on every screen.** They remain in the About text, the Model card, the page description in the HTML metadata, and in every agent reply, where code, not the model, adds the disclaimer. The project context says the synthetic and fictional status is stated in the README, the UI and the data files; the UI statement is now the title, the About tab and the Model card. This is the owner's decision; the risk is a visitor who never opens those tabs reading the demo as a real tool. The reply disclaimer limits that risk for anyone who runs a check.

**3. The no-integration clause stays.** The page still must not claim FHIR, vendor or real-system integration. With the "MOCK EHR" label gone, the test for it checks the page text for HL7 and Epic.

**4. Two requirements are touched, the second after an archive.** The About-tab requirement comes from `add-about-tab`, which is merged but not archived, so it is not in the main spec yet. This change's delta edits it, so `add-about-tab` must be archived first.

## Risks

- A visitor sees no disclaimer before using the demo, other than the title. Mitigation: the reply disclaimer, the About tab, and the title.
- Archiving out of order fails the About-tab modification. Mitigation: the order is stated in the proposal and in the tasks.
