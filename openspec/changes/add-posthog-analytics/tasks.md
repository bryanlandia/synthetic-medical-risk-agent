## 1. Configuration and the event layer

- [ ] 1.1 Add `posthog-js` (pinned) to `web/package.json` and write `web/lib/analytics.ts`: the init options (memory persistence, no autocapture, no automatic page view, identified-only profiles, masked inputs, first-party host), the `ref` sanitizer, the Do Not Track and Global Privacy Control check, and event helpers that do nothing when analytics is off. Eval: Playwright unit tests (no browser) assert each option, that `ref` reduces `"Ode!!<script>"` to `"odescript"` and an empty or 100-character value correctly, and that every event helper rejects a value outside its fixed label set.
- [ ] 1.2 Add the `/ingest` rewrites and `skipTrailingSlashRedirect` to `web/next.config.mjs`, with the region from `NEXT_PUBLIC_POSTHOG_HOST` and an optional output directory from an environment variable. Check the rewrite shape against PostHog's current Next.js documentation. Eval: the production build still passes the existing tests with no key set.

## 2. The component, the notice and the wiring

- [ ] 2.1 Add `web/components/Analytics.tsx` (dynamic import, start only with a key and no DNT or GPC, one page view with `ref`) and the footer notice with the "Don't record my visit" control, rendered from the layout only when a key is set. Eval: with no key the page has no notice and no analytics request.
- [ ] 2.2 Put `ph-no-capture` on the free-text tab's panel and call the event helpers from `Demo.tsx`, `ChartTab.tsx` and `FreeTextTab.tsx` (`tab_opened`, `check_run`, `example_used`, `message_sent`). Eval: the class is present on that panel and on no other tab.

## 3. Tests

- [ ] 3.1 Add the analytics build to the Playwright setup: a second production build with a test key and a stub host in its own output directory, served on its own port, and a stub PostHog server that records what it receives. Eval: both servers start and the existing 36 tests still pass.
- [ ] 3.2 Add `analytics.spec.ts` for the scenarios in the design (notice and first-party path; `ref` on the page view; label-only events; no typed text, reply or probability in any request body; no cookie or storage entry; opt-out; Do Not Track and Global Privacy Control; a sanitized `ref`). Eval: each test fails if its protection is removed (checked once by hand for the typed-text and opt-out tests).

## 4. Documentation and the owner's steps

- [ ] 4.1 Update `web/README.md` (the two variables, the PostHog project settings in the design, how to make `?ref=` links, what the page can and cannot tell the owner, and the notice) and extend `deploy/check-env.sh` to fail if a web project's preview environment has `NEXT_PUBLIC_POSTHOG_KEY`. Eval: the README lists both variables and the check script catches a preview key.
- [ ] 4.2 Owner-run: in PostHog confirm session replay is on, client IP is discarded and the authorized URL is the production domain; set the two variables on the web project, production only; redeploy; open the page with `?ref=test`, use each tab, then confirm the page view with `ref`, the events and a recording appear, and that the free-text tab is a placeholder in the recording. Record the outcome in the README.
- [ ] 4.3 Run the web tests and typecheck, the Python suites that read `web/content/` (`training` and `evals` freshness tests) and `openspec validate add-posthog-analytics --strict`.
