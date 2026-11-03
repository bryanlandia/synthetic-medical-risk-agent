# web

**All data is synthetic and the disease is fictional. Nothing here is medical advice.** A public demo page in which the visitor is a
**neurology supervisor** reviewing a queue of 30 prepared PET-CT request packets (nothing is connected to a real system; no FHIR,
no vendor software). The guards and the evals around the agent are the real subject; the page is how a visitor sees them work.

- **Queue**: 30 invented requests from the dev split, each prepared by a (simulated) clinician for one of ten fictional insurers.
  The page opens with "What are the review and packet for?" in plain words; the same text is a help dialog on every case. Opening a case
  makes one request to the packet route and keeps the result in the browser: the chart, the checklist against the fictional
  policy with cited evidence, what is missing, a checked summary and the model's estimate as context. The supervisor then
  releases it (blocked while any criterion is unknown; their own written rationale is needed if one is unmet), returns it with a
  note, or closes it. Nothing is sent anywhere. A released packet has a cover sheet, an audit trail, copy and print.
- **Estimate a risk** (second scenario): sliders for the eight labs (each can be "not done") and toggles for the five symptoms of an invented
  patient, opening on a borderline one; a dial with the model's estimate, its band and a bar for each input, from `/api/estimate` (no
  language model, its own rate limit). "Send this patient to the assistant" writes the patient out as a short note (the message the service
  returns, so the page has no copy of the template) and shows the assistant's number beside the dial's; three buttons add a hidden
  instruction, a treatment question or an off-topic question. A collapsed box still takes your own text. It starts from no queue case, edits
  no recorded value and stores nothing.
- **How it works** (menu): the **Model card** (with a check that it describes the model that is running) and **About this project**
  (from `content/about.md`).

Progress (statuses, packets, return notes, rationales) is kept in this browser's `localStorage` and nothing else; "Reset demo"
clears it. A visit that changes nothing writes nothing. The design uses Material UI (MUI) with one theme in `lib/theme.ts`, whose
colour pairs are tested for 4.5:1 contrast; no font, script or image comes from another site. Every simulated thing carries a quiet
"Demo" note (`lib/copy.ts`), and a strip on every screen says everything is invented.

**Writing the About text.** Edit `content/about.md` like any markdown file (headings, lists, tables and links all render; images do not, and links open in a new tab). It starts as an outline: each section has a draft paragraph that begins `*Suggested content:*`. Replace a paragraph with your own text and delete the marker; `grep -n 'Suggested content' content/about.md` lists the sections still unwritten. Take any figures from `evals/README.md` and the result files, not from memory, so they stay checkable.

## How a request travels

```
browser --> /api/analyze (this app's server route) --> agent service (Vercel, Python) --> Claude Haiku 5.5
              adds the shared secret and the                 guards, scoring tool, reply check
              visitor address, returns a whitelist           counters in a shared store (Upstash Redis)
```

The browser never holds the shared secret or the agent's address (`AGENT_URL` has no `NEXT_PUBLIC_` prefix). A Playwright test
builds the app and searches everything sent to the browser for both.

The route passes on the report's `interval` and `gaps` only when they are well formed (probabilities in [0, 1], a known kind); anything else is dropped. The
chart in a case shows each lab's reference range and an H or L flag, both written into `cases.json` by `evals demo-cases` (judged after
conversion to the lab's usual unit), so the browser does no unit logic. Each case's `received` is a fictional date and time in fictional Eastern time ("2026-11-02 07:45"), written by the same builder (three working days, ten cases a day) and shown as "2 Nov 2026, 07:45 ET" in every visitor's zone (`formatReceived` in `lib/copy.ts`).
Each part of a case is labelled with what produced it (a model, plain code, the simulated preparer or the supervisor): one table, `PRODUCED` in `lib/copy.ts`, feeds the labels, the checklist's Source column and the "What produced this page?" key, so they cannot drift. The report card labels the interval "Range if the missing results are
obtained": it covers findings not on the record and does not include uncertainty in the model itself, so it is never called a confidence interval. Nothing on the page edits a recorded value.


**The packet route.** `/api/packet` works like `/api/analyze`: it keeps the secret and the service address, accepts only a message and the
preparer's answers for C3 to C6 (yes, no or not yet answered; anything else is 422), and passes on a whitelist (the six criteria
with status and cited evidence, the gaps, the summary and whether it came from the model or the template, and the model's estimate as
context). The criteria wording on the page is `content/pet_ct_policy.json`, a copy of `risk_model/src/risk_model/policy/pet_ct_k17.json`;
a test fails if they differ, so copy the file again when the policy changes. C5 is shown in a positive wording (`criterionText` in `lib/copy.ts`, display only) so that a Yes means the criterion holds. The supervisor's note and rationale stay in the browser
and are never sent. Printing shows the released packet and the synthetic-data notice only.

**The estimate route.** `/api/estimate` forwards the labs and symptoms the visitor set (and nothing else; anything else is 422) to the service's `/estimate`, with the secret and the visitor address, and passes on a whitelist (the probability, band, score, starting point, the thirteen breakdown rows, the generated message and the model hash). The page has no copy of the model or of the note template: the percentage, the bars and the message all come from the service. `lib/estimator.ts` sends at most one request every 150 ms while a control moves and once more when it stops, drops an answer older than the one on screen, keeps the last estimate on a 429, and shows a waking-up message after 1.5 s. The opening patient and the lab limits are `content/estimate.json`, written by `uv run python -m risk_model.estimate_start` (a test in `risk_model/` and one here fail if it is stale).

**Bundle size.** First-load JS for the page was 157 kB before the Material redesign and is 259 kB after it (MUI and the 30-case file);
the shared JS of the app is unchanged at 103 kB.

## Run it locally (free: the scripted model, no key)

```
cd agent && AGENT_SCRIPTED_MODEL=1 AGENT_SHARED_SECRET=local-secret AGENT_RELAX_LIMITS=1 AGENT_ENV=development uv run agent serve --port 8000
cd web && npm install --ignore-scripts   # once
AGENT_URL=http://127.0.0.1:8000 AGENT_SHARED_SECRET=local-secret npm run dev
```

Tests (from `web/`, with `uv` on the PATH): `npm test` builds the production app, starts the scripted agent and the app, and runs
28+ Playwright tests (the forwarding and error mapping, the chart flow, free text, the model card, no leaked secrets).
`PW_USE_DEV=1 npm test` uses the dev server instead of building.

Committed content in `content/` is generated, and tests keep it current:
`uv run evals demo-cases` (from `evals/`) writes `cases.json`; `uv run training card` (from `training/`) refreshes
`model-card.md`.

## Visit and click counts (PostHog)

The page counts visits and clicks, anonymously, with PostHog. It does **not** record screens, identify anyone, store anything in
the browser, or send anything a visitor types or the agent answers. It is **off unless** `NEXT_PUBLIC_POSTHOG_KEY` is set when
the app is built, so local runs, tests and previews count nothing.

| Variable (web project, production only) | Meaning |
|---|---|
| `NEXT_PUBLIC_POSTHOG_KEY` | the PostHog project key (a public identifier, not a secret) |
| `NEXT_PUBLIC_POSTHOG_HOST` | your region's ingest host: `https://us.i.posthog.com` (default) or `https://eu.i.posthog.com` |

What is sent: one `$pageview` per load, `ui_click` with the element's name (`tab:about`, `patient:<slug>`, `run_check`,
`sent_message_expander`, `example:<slug>`, `send_free_text`, `link:<host>` for links that leave the site), and `result_shown`
with the source and `scored`, `declined` or `error`. Names live in the markup as `data-track` and are checked against a fixed
list in `lib/analytics.ts`; automatic capture is off. A footer notice says this and has a "Don't count my visit" button (the
choice is kept in local storage, and pressing it is not itself counted). Do Not Track and Global Privacy Control start nothing.
Requests go to `/ingest` on the site itself, which the server forwards to PostHog (an ad blocker then hides far fewer visits).

**Telling people apart.** Give each recipient their own link with a `ref`, for example `https://vk-check.vercel.app/?ref=ode`,
and filter by `ref` in PostHog. The page cannot tell which company a visitor works at; the link is the only way.

**PostHog project settings (do these once).**
1. Project Settings, Web Analytics: turn on **Cookieless server hash mode**. Without it PostHog ignores cookieless events, and the
   page counts nothing.
2. Authorized URLs: only the production address.
3. Leave session replay off. Cookieless unique visitors are approximate (a hash of address and browser that changes daily).

`deploy/check-env.sh <agent-project> <web-project>` also fails if the web project's preview environment holds the key.

**Checked on production (2026-11-01).** The key is in the built JavaScript, `/ingest` forwards to PostHog (200), and a page view with
`?ref=test` arrives from Safari with the notice shown. A browser with Do Not Track on (Firefox here) shows no notice and sends
nothing, as intended. Automated browsers (Playwright) are dropped by PostHog's own bot filter unless they hide the user agent,
`navigator.webdriver` and the client-hint brands, as `tests/analytics.spec.ts` does.

## Deploy (Vercel only, two projects from this repository)

| Project | Root Directory | Framework | Built from |
|---|---|---|---|
| agent service | the repository root | Other | `index.py`, `requirements.txt`, `vercel.json`, `.vercelignore` (a Python function) |
| web | `web/` | Next.js | this folder |

Environment variables (set in each project's settings or with `vercel env add`; never in a file or in client code):

| Variable | Project | Production | Preview | Purpose |
|---|---|---|---|---|
| `AGENT_SHARED_SECRET` | both | same value in both | same value in both | the web route sends it; the service rejects any call without it |
| `ANTHROPIC_API_KEY` | agent | set | **not set** | the model; a preview URL must not be able to spend money |
| `AGENT_ENV` | agent | `production` | `preview` | `production` refuses the scripted model, relaxed limits and a missing store |
| `AGENT_SCRIPTED_MODEL` | agent | not set | `1` | the rule-based test model: free, no key |
| `AGENT_DAILY_BUDGET_USD` | agent | `1.0` | default | the daily dollar cap (about 1,600 requests at $0.0006) |
| `AGENT_RATE_PER_MINUTE`, `AGENT_RATE_PER_DAY` | agent | `10`, `200` | default | per visitor |
| `AGENT_STORE_URL`, `AGENT_STORE_TOKEN` | agent | set (Upstash REST URL and token) | not set | the shared counters; required in production |
| `AGENT_URL` | web | the agent project's production URL | the same or a preview agent | where the route forwards; server-side only |

`deploy/check-env.sh <agent-project>` (needs the Vercel CLI, reads names only) fails if a preview holds the API key or a
production project is missing one of the above. After a deploy, `AGENT_SHARED_SECRET=... uv run agent smoke --url https://<agent-url>`
(from `agent/`) checks the model hash, one scored request and one declined request.

**Retry-After.** When a visitor is over a limit the service answers `429` with `Retry-After` (seconds). The route passes the
header on and the page tells the visitor how long to wait. A script that calls the service should wait that long before it
retries. When the day's budget is used up the service answers `503` (`daily_budget_used`) until the next UTC day.

**Notes.** The free Vercel plan is for non-commercial use, which a portfolio demo is. Rate limits use fixed one-minute and
one-day windows in the shared store, so a visitor can briefly send up to twice the per-minute limit across a window boundary;
the daily dollar cap is the real bound. `npm audit` reports PostCSS issues inside Next.js 15.5.28 (the version `rating_ui`
also uses); PostCSS runs only at build time on this repository's own CSS, and moving to a newer Next.js is a separate change.

## Deployed

| | Address | Project |
|---|---|---|
| The demo page | https://vk-check.vercel.app | `vk-check` (Root Directory `web/`) |
| The agent service | https://vk-agent-spike.vercel.app | `vk-agent-spike` (Root Directory: the repository root; the name is left from the spike) |

First deployed and checked on 2026-10-27: the agent reports Haiku 5.5 and the committed model hash `414c2d467c87…`; `uv run agent
smoke` passed against it (model hash, one scored request, one decline); `deploy/check-env.sh vk-agent-spike` passed; the page was
clicked through (the queue and a case, the Estimate a risk sliders and assistant buttons, the model card and its hash check). The addresses are public; the
shared secret is what keeps the agent from being called around the page, and the daily cap and limits bound what a call can spend.

## What changes with real data

This page shows the framing, not an integration. In a real deployment the panel would live inside an existing EHR and read the
structured labs and notes already in the chart (through that system's own interfaces), the request would carry a verified
user and patient context, nothing would be pasted, and the risk model would be trained and validated on real data under the
rules that apply to it. None of that is built or claimed here.
