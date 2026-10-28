## 1. Page (done on branch `remove-banner`, commit `bb44a69`)

- [x] 1.1 Delete `web/components/Banner.tsx` and its use in `web/app/layout.tsx`; delete the `.banner` styles in `web/app/globals.css`.
- [x] 1.2 Change the title in `web/components/Demo.tsx` to "Decision support for Velorin-Kessler Syndrome diagnosis (fictional disease)" and the first tab to "Sample patient charts".
- [x] 1.3 Update `web/tests/demo.spec.ts` (title on every tab, no HL7 or Epic claim, no banner assertion in the About test), `web/tests/analytics.spec.ts` and `web/README.md` for the new tab name; the full Playwright suite passes.

## 2. Spec

- [x] 2.1 Archive `add-about-tab` first (its requirement is edited by this change's delta).
- [x] 2.2 `openspec validate remove-synthetic-banner --strict` passes.
- [x] 2.3 Merge `remove-banner`, then archive this change; confirm the main `web-demo` spec has the renamed requirement and no banner scenario.
