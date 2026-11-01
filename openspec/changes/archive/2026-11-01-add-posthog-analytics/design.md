# Design

## Context

`web/` is a Next.js 15.5 App Router app with a statically rendered page (`app/page.tsx`), a client component with four tabs (`Demo.tsx`), a layout with the synthetic-data banner, and Playwright tests that build the production app and run it with the scripted agent on port 3200. A test already searches the browser-visible files for the shared secret and the agent's address; a PostHog project key is a different thing (a public, write-only identifier by design) and is allowed in client code. The owner has a PostHog account and wants visitor counts and click counts; screen recording is not wanted. See proposal.md.

## Goals / Non-Goals

**Goals:** a visit count and a per-element click count, switched on only in production; nothing a visitor types or reads from the agent ever leaves the page; a visible notice; a way to tell recipients apart.

**Non-Goals:** screen recording or session replay, identifying visitors, funnels, experiments, feature flags, surveys, a consent gate (the owner chose counting by default), server-side tracking, and any change to the agent or the evals. A Claude-side PostHog connector is not part of this change.

## Decisions

**1. The SDK is `posthog-js`, pinned (1.440.0 at the time of writing), loaded by a dynamic import only when a key is configured.** With no `NEXT_PUBLIC_POSTHOG_KEY` the code path never runs and the SDK is never fetched, so local runs, tests and previews send nothing. The key is inlined at build time; it is a public project identifier, unlike `AGENT_SHARED_SECRET`. Alternative: PostHog's snippet in the HTML head; rejected because it loads on every build and is harder to test off.

**2. Anonymous and storage-free, using PostHog's cookieless mode for the visitor count.** Initialization turns off session recording and automatic capture, sends one explicit page view, never calls identify, honors Do Not Track, and does not start at all if `navigator.doNotTrack` is "1" or `navigator.globalPrivacyControl` is true. For counting visitors without a stored identifier the design uses the SDK's cookieless mode (a daily server-side hash instead of an id on the device); the exact option, and any project setting it needs, are checked against PostHog's current documentation in task 1.1. If cookieless mode is not usable, the fallback is memory-only persistence, which still counts page views and clicks but cannot link a reload or a return visit to one person, so "unique visitors" would be an overcount; the README would then say so. The opt-out flag is the one thing stored (local storage), so an opted-out visitor stays opted out. The page keeps its own opt-out gate in front of the SDK and in its `before_send` hook, because the SDK's own opt-out was found not to stop capture in cookieless mode; the press of the opt-out button is itself not counted.

**3. Clicks are named in the markup, not harvested.** Each countable element carries a `data-track` attribute with its name, and one delegated click listener finds the nearest such element and sends `ui_click` with `element` set to that name. The names: `tab:<tab>`, `patient:<slug>`, `run_check`, `sent_message_expander`, `example:<slug>`, `send_free_text`, and `link:<host>` for links that leave the site (the About and model-card links, set in the shared markdown component from the link's host alone). A closed list and patterns in `lib/analytics.ts` validate each name before it is sent; anything else is dropped. Automatic capture stays off, because it would send element text and attributes the code does not control. Alternative: PostHog autocapture; rejected for that reason.

**4. Events carry labels, never content.** Besides `$pageview` (with `ref`) and `ui_click`, the page sends `result_shown {source: "chart" | "free_text", kind: "scored" | "declined" | "error"}` so the owner can see whether checks complete. No message text, reply, probability or report is ever passed to the SDK. A unit test builds every event and fails if a value outside the allowed labels appears.

**5. First-party path.** `next.config.mjs` rewrites `/ingest/static/:path*` and `/ingest/array/:path*` to the region's assets host and `/ingest/:path*` to the region's ingest host (the static and array rules above the catch-all, as PostHog's guide says), with `skipTrailingSlashRedirect`, and the SDK uses `api_host: "/ingest"`. The region host comes from `NEXT_PUBLIC_POSTHOG_HOST` (default the US ingest host), read when the app is built. The details follow PostHog's documented Next.js proxy recipe and are checked against its current documentation when the task is done. The rewrite only reaches PostHog's own hosts. Alternative: direct requests to PostHog; rejected because ad blockers, common among the likely visitors, would hide most visits.

**6. The notice.** A slim footer bar on every screen, shown only when analytics is on: "Visits to this demo and clicks on its buttons are counted anonymously. Nothing you type is collected and your screen is not recorded." with a "Don't count my visit" button that calls `opt_out_capturing()` and changes the text to "Counting is off for this visit." No consent wall.

**7. Telling recipients apart.** `?ref=<label>` is read once, reduced to lowercase letters, digits, hyphen and underscore, cut to 32 characters, dropped if empty, and registered as a property on every event of the visit. The owner gives each recipient a link such as `https://…/?ref=ode`. With no identification, this is the only way to tell visitors apart, and the README says so plainly: the page cannot tell which company a visitor works at.

**8. PostHog project settings (owner-run).** "Cookieless server hash mode" turned on under Project Settings, Web Analytics (without it cookieless events are ignored); authorized URLs limited to the production domain; "Discard client IP data" on unless cookieless mode needs the IP for its hash (then the README says which and why); person profiles for anonymous events off; session replay left off. These are in the dashboard, not the repository, so the README lists them and a task has the owner confirm them.

**9. Tests.** A second production build is made with analytics on (`NEXT_PUBLIC_POSTHOG_KEY=phc_test`, host pointing at a local stub, its own output directory so the two builds do not collide) and served on its own port, with a small stub server standing in for PostHog that records what it receives. Playwright then checks: the notice and the first-party path; exactly one page view per load, carrying `ref`; a named `ui_click` for each countable element and none for empty space or typing; no request body contains text typed in the free-text box, the reply or the probability; no recording script is requested; no cookie or storage entry is written; the opt-out button stops further requests; Do Not Track and Global Privacy Control start nothing; a hostile `ref` is reduced. The existing build (no key) is checked to make no analytics request and show no notice.

## Risks / Trade-offs

- **Counting by default, with no consent gate.** Visitors from places that require prior consent for tracking could object. The mitigations are the visible notice, the opt-out, honoring Do Not Track and Global Privacy Control, no identifiers or storage on the device, no recording, and no typed content. The owner has chosen this; moving to an opt-in banner later is a small change in one component.
- **Unique-visitor numbers are approximate** under cookieless mode (a visitor on a new network or browser counts again, and one hash is shared by people behind one address) and are overcounted if the fallback is used.
- **Names in the markup can drift.** A test lists the elements that must carry a name, so removing one fails the build.
- **Free-plan limits** on events are the owner's PostHog plan, not set here. A busy day could exhaust them; counting stops, the demo does not.
- **The rewrite makes the site a narrow relay to PostHog** for `/ingest` paths only.

## Open Questions

None. The region (US or EU) is the owner's account setting, supplied through `NEXT_PUBLIC_POSTHOG_HOST`.
