# Design

## Context

`web/` is a Next.js 15.5 App Router app with a statically rendered page (`app/page.tsx`), a client component with four tabs (`Demo.tsx`), a layout with the synthetic-data banner, and Playwright tests that build the production app and run it with the scripted agent on port 3200. A test already searches the browser-visible files for the shared secret and the agent's address; a PostHog project key is a different thing (a public, write-only identifier by design) and is allowed in client code. The owner has a PostHog account and wants to know whether the people the page was written for have looked at it. See proposal.md.

## Goals / Non-Goals

**Goals:** page views, recordings and a handful of usage events, switched on only in production; recordings that cannot contain what a visitor types or what the agent says about it; a visible notice; a way to tell recipients apart.

**Non-Goals:** identifying visitors, funnels or experiments, feature flags, surveys, a consent gate (the owner chose recording by default), any server-side tracking, any change to the agent or the evals. A Claude-side PostHog connector is not part of this change.

## Decisions

**1. The SDK is `posthog-js`, pinned (1.440.0 at the time of writing), loaded by a dynamic import only when a key is configured.** With no `NEXT_PUBLIC_POSTHOG_KEY` the code path never runs and the SDK is never fetched, so local runs, tests and previews send nothing. The key is inlined at build time; it is a public project identifier, unlike `AGENT_SHARED_SECRET`. Alternative: PostHog's snippet in the HTML head; rejected because it loads on every build and is harder to test off.

**2. Anonymous by construction.** Initialization sets `persistence: "memory"` (no cookie, local storage or session storage), `person_profiles: "identified_only"` and never calls identify, `autocapture: false` (so clicks and field values are not harvested), `capture_pageview: false` (a single explicit page view is sent), and `respect_dnt: true`. If `navigator.doNotTrack` is "1" or `navigator.globalPrivacyControl` is true, the SDK is not started at all. The cost of memory persistence is that a reload is a new session and a returning visitor cannot be linked; for the question "did anyone look" that is acceptable. The opt-out flag is the one thing stored (in local storage) so an opted-out visitor stays opted out.

**3. What the recordings can and cannot show.** `session_recording` uses `maskAllInputs: true`. The free-text tab's whole panel (text box and result card) carries the class `ph-no-capture`, which PostHog replaces with a placeholder in recordings, because the reply there is derived from what the visitor typed. The chart, About and model-card tabs are recorded as they are: their content is the committed synthetic demo content. Events carry labels only: `tab_opened {tab}`, `check_run {patient}` (the slug), `example_used {example}` (the example's label), `message_sent {result}` where result is `scored`, `declined` or `error`, and the page view with `ref`. No message text, reply, probability or report is ever passed to the SDK; a unit test builds each event and fails if a value outside a fixed set of labels appears.

**4. First-party path.** `next.config.mjs` rewrites `/ingest/static/:path*` to the region's assets host and `/ingest/:path*` to the region's ingest host, with `skipTrailingSlashRedirect`, and the SDK uses `api_host: "/ingest"`. The region host comes from `NEXT_PUBLIC_POSTHOG_HOST` (default the US ingest host), read when the app is built. The details follow PostHog's documented Next.js proxy recipe and are checked against its current documentation when the task is done. The rewrite only reaches PostHog's own hosts. Alternative: direct requests to PostHog; rejected because ad blockers, common among the likely visitors, would hide most visits.

**5. The notice.** A slim footer bar on every screen, shown only when analytics is on: "Visits to this demo, including screen sessions, are recorded anonymously to see whether it is being used. Text you type is not recorded." with a "Don't record my visit" button that calls `opt_out_capturing()` and changes the text to "Recording is off for this visit." No consent wall; no cookies to disclose.

**6. Telling recipients apart.** `?ref=<label>` is read once, reduced to lowercase letters, digits, hyphen and underscore, cut to 32 characters, dropped if empty, and registered as a property on every event of the visit. The owner gives each recipient a link such as `https://…/?ref=ode`. With IP discarded and no identify, this is the only way to tell visitors apart, and the README says so plainly: the page cannot tell which company a visitor works at.

**7. PostHog project settings (owner-run).** Session replay on; "Discard client IP data" on; authorized URLs limited to the production domain; person profiles for anonymous events off. These are in the dashboard, not the repository, so the README lists them and a task has the owner confirm them.

**8. Tests.** A second production build is made with analytics on (`NEXT_PUBLIC_POSTHOG_KEY=phc_test`, host pointing at a local stub, its own output directory so the two builds do not collide) and served on its own port, with a small stub server standing in for PostHog that records what it receives. Playwright then checks: the notice and the first-party path; the page view carries `ref`; each named event carries only labels; no request body contains text typed in the free-text box, the reply or the probability; no cookie or storage entry is written; the opt-out button stops further requests; Do Not Track and Global Privacy Control start nothing; the free-text panel has the blocking class. The existing build (no key) is checked to make no analytics request and show no notice. The recorder's own script is PostHog's and is not served by the stub, so what a recording looks like is confirmed once by the owner in PostHog after deploying.

## Risks / Trade-offs

- **Recording by default, with no consent gate.** Visitors from places that require prior consent for recording could object. The mitigations are the visible notice, the opt-out, honoring Do Not Track and Global Privacy Control, no identifiers or storage, and blocking the one place visitors type. The owner has chosen this; moving to an opt-in banner later is a small change in one component.
- **Blocking depends on a class name.** A test asserts the class on the free-text panel, and the owner confirms in a real recording after deploying.
- **A recorder adds weight** to a page that is otherwise tiny; it loads after the page and only in production.
- **Free-plan limits** on recordings and events are the owner's PostHog plan, not set here. A busy day could exhaust them; analytics stops, the demo does not.
- **The rewrite makes the site a narrow relay to PostHog** for `/ingest` paths only.

## Open Questions

None. The region (US or EU) is the owner's account setting, supplied through `NEXT_PUBLIC_POSTHOG_HOST`.
