# Proposal

## Why

The demo page is meant to be opened by specific people, including the team the project was written for, and the owner has no way to tell whether anyone has looked at it or which parts they used. The owner has a PostHog account and wants two things: how many visitors there are, and which interface elements get clicked. Screen recording is out of scope; other tools will cover it. A page that counts strangers still needs rules about what it may collect, and it takes typed text from them, so those rules are part of the change.

## What Changes

- Add the PostHog JavaScript SDK to the web app, started only when a project key is configured, so local runs, tests and previews send nothing.
- **Count visitors** with one page view per page load, sent without cookies or any browser storage, using PostHog's cookieless mode so the dashboard can show approximate unique visitors without storing an identifier on the visitor's device.
- **Count clicks by element name**: tabs, demo patients, the Run V-K check button, the "message sent" expander, the example buttons, the Send button, the opt-out control, and links that leave the site (the host only). Each click is one event with a fixed name, not a harvest of the page's text.
- **Never collect what a visitor types** or what the agent answers, and never record the screen.
- Show a **one-line notice** on every screen saying visits and clicks are counted anonymously, with a "Don't count my visit" control, and honor Do Not Track and Global Privacy Control. There is no consent gate: counting is on by default, which is the owner's choice.
- Send events **through the site's own address** (a rewrite), so ordinary ad blockers do not hide most visits.
- Let the owner tell recipients apart with a **`?ref=` link parameter** (for example `?ref=ode`), recorded with each visit.
- Document the PostHog project settings the owner needs and the environment variables.

## Capabilities

### New Capabilities
- `usage-analytics`: what the page counts and what it must never collect, how visitors and clicks are named, the notice and opt-out, the signals it honors, when analytics is off, and how a recipient link is told apart.

### Modified Capabilities
- `deployment`: the analytics key and host are set only in the production environment.

## Impact

- Code: `web/next.config.mjs` (a rewrite and an optional output directory), a new `web/components/Analytics.tsx`, the notice in `web/app/layout.tsx`, `data-track` names on the interface elements in `Demo.tsx`, `ChartTab.tsx`, `FreeTextTab.tsx` and the shared markdown links, `web/package.json` (one pinned dependency).
- Tests: Playwright, with a second build that has analytics switched on and a local stub in place of PostHog.
- Services: the owner's existing PostHog project (region and a project setting for cookieless counting), and two new environment variables on the web project, production only.
- No change to the agent, the model, the evals or any recorded result.
- Ordering: independent of `add-about-tab`, which is merged and not yet archived.
