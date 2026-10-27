## 1. Configuration and the event layer

- [ ] 1.1 Add `posthog-js` (pinned) to `web/package.json` and write `web/lib/analytics.ts`: the init options (no session recording, no automatic capture, no automatic page view, cookieless counting as the design describes after checking PostHog's current documentation), the `ref` sanitizer, the Do Not Track and Global Privacy Control check, the closed list and patterns of click names, and event helpers that do nothing when analytics is off. Eval: Playwright unit tests (no browser) assert each option, that `ref` reduces `"Ode!!<script>"` to `"odescript"` and an empty or 100-character value correctly, and that a click name or event label outside the allowed set is dropped.
- [ ] 1.2 Add the `/ingest` rewrites and `skipTrailingSlashRedirect` to `web/next.config.mjs`, with the region from `NEXT_PUBLIC_POSTHOG_HOST` and an optional output directory from an environment variable. Check the rewrite shape against PostHog's current Next.js documentation. Eval: the production build still passes the existing tests with no key set.

## 2. The component, the notice and the wiring

- [ ] 2.1 Add `web/components/Analytics.tsx` (dynamic import, start only with a key and no DNT or GPC, one page view with `ref`, one delegated click listener) and the footer notice with the "Don't count my visit" control, rendered from the layout only when a key is set. Eval: with no key the page has no notice and no analytics request.
- [ ] 2.2 Add `data-track` names to the tabs, demo patient buttons, Run V-K check, the expander summary, the example buttons, the Send button, the opt-out control and, in the shared markdown component, outbound links (host only); send `result_shown` from `Demo.tsx`. Eval: a test lists every element that must carry a name and fails if one loses it.

## 3. Tests

- [ ] 3.1 Add the analytics build to the Playwright setup: a second production build with a test key and a stub host in its own output directory, served on its own port, and a stub PostHog server that records what it receives. Eval: both servers start and the existing 36 tests still pass.
- [ ] 3.2 Add `analytics.spec.ts` for the scenarios in the design (notice and first-party path; one page view with `ref`; a named click for each countable element and none for empty space or typing; no typed text, reply or probability in any request body; no recorder requested; no cookie or storage entry; opt-out; Do Not Track and Global Privacy Control; a sanitized `ref`). Eval: each test fails if its protection is removed (checked once by hand for the typed-text and opt-out tests).

## 4. Documentation and the owner's steps

- [ ] 4.1 Update `web/README.md` (the two variables, the PostHog project settings in the design, how to make `?ref=` links, what the page can and cannot tell the owner, the click names, and the notice) and extend `deploy/check-env.sh` to fail if a web project's preview environment has `NEXT_PUBLIC_POSTHOG_KEY`. Eval: the README lists both variables and the check script catches a preview key.
- [ ] 4.2 Owner-run: in PostHog confirm the authorized URL, the IP and cookieless settings; set the two variables on the web project, production only; redeploy; open the page with `?ref=test`, use each tab, patient, example and the expander, then confirm in PostHog one page view with `ref`, the named clicks, and that no recording exists. Record the outcome in the README.
- [ ] 4.3 Run the web tests and typecheck, the Python suites that read `web/content/` (`training` and `evals` freshness tests) and `openspec validate add-posthog-analytics --strict`.
