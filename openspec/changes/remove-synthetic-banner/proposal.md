# Proposal

## Why

The web page carries a banner on every screen saying the data is synthetic, the disease is fictional and the output is not medical advice, plus a "MOCK EHR" label. The owner has decided the page is clear enough without it: the title already names the disease as fictional, and the About and Model card tabs say the rest. The `web-demo` spec still requires the banner, so the spec and the page disagree. The code change is already made on branch `remove-banner` (commit `bb44a69`); this change brings the spec in line with it.

## What Changes

- Remove the banner and the mock-EHR label from every screen.
- The page title now reads "Decision support for Velorin-Kessler Syndrome diagnosis (fictional disease)", so the fictional status is still on every screen.
- The first tab is renamed "Sample patient charts".
- The requirement that the page not claim FHIR, vendor or real-system integration stays.
- The About-tab requirement no longer says the tab carries the banner.
- **BREAKING** (to the spec only): "synthetic data" and "not medical advice" are no longer required on every screen. They remain in the About text, the Model card, and every agent reply (the disclaimer is added by code, not by the model).

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `web-demo`: the banner requirement is replaced by one for the fictional-disease title and the no-integration claim; the About-tab requirement drops its banner clause.

## Impact

- Code (already done on `remove-banner`): `web/components/Banner.tsx` deleted, `web/app/layout.tsx`, `web/components/Demo.tsx`, `web/app/globals.css`.
- Tests (already done): `web/tests/demo.spec.ts`, `web/tests/analytics.spec.ts`; the banner test now checks the title on every tab and that the page claims no HL7 or Epic integration.
- Docs: `web/README.md` tab name.
- Ordering: `add-about-tab` adds the About-tab requirement that this change edits. Archive `add-about-tab` first.
