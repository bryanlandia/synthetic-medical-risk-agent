# Proposal

## Why

The demo page is meant to be opened by specific people, including the team the project was written for, and the owner has no way to tell whether anyone has looked at it, which tab they used, or whether they got stuck. The owner has a PostHog account and wants page views, a few usage events and screen recordings of visits. A page that records visitors needs rules about what it may capture, and the page takes typed text from strangers, so those rules are part of the change and not an afterthought.

## What Changes

- Add the PostHog JavaScript SDK to the web app, started only when a project key is configured, so local runs, tests and previews send nothing.
- Record **page views, session recordings and a few named events** (a tab opened, a demo patient checked, an example used). Events carry labels such as a patient slug or an example name, never message text, results or replies.
- Make the recordings **anonymous and masked**: typed text is masked, nothing is stored in the browser's cookies or local storage, and nobody is identified.
- Show a **one-line notice** on every screen saying visits are recorded, with a "Don't record my visit" control, and honor Do Not Track and Global Privacy Control. There is no consent gate: recording is on by default, which is the owner's choice.
- Send events **through the site's own address** (a rewrite), so ordinary ad blockers do not hide most visits.
- Let the owner tell recipients apart with a **`?ref=` link parameter** (for example `?ref=ode`), recorded with each visit.
- Document the PostHog project settings the owner needs (session replay on, IP discarded, allowed domain) and the environment variables.

## Capabilities

### New Capabilities
- `usage-analytics`: what the page records and what it must never record, the notice and opt-out, the opt-out signals it honors, when analytics is off, and how a recipient link is told apart.

### Modified Capabilities
- `deployment`: the analytics key and host are set only in the production environment.

## Impact

- Code: `web/next.config.mjs` (a rewrite and an optional output directory), a new `web/components/Analytics.tsx`, the notice in `web/app/layout.tsx`, event calls in `Demo.tsx`, `ChartTab.tsx` and `FreeTextTab.tsx`, `web/package.json` (one pinned dependency).
- Tests: Playwright, with a second build that has analytics switched on and a local stub in place of PostHog.
- Services: the owner's existing PostHog project (region and project settings), and two new environment variables on the web project, production only.
- No change to the agent, the model, the evals or any recorded result.
- Ordering: independent of `add-about-tab`, which is merged and not yet archived.
