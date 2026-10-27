# web

**All data is synthetic and the disease is fictional. Nothing here is medical advice.** A public demo page: a **mock EHR** chart
(not connected to any real system; no FHIR, no vendor software) with a decision-support panel that runs the risk check on what
is on the chart. The guards and the evals around the agent are the real subject; the page is how a visitor sees them work.

- **Patient chart**: pick one of four invented patients (from the dev split, with their messages pre-rendered by the eval
  harness), read the labs and note, open "Message sent to the agent" to see the exact text, and press "Run V-K check".
- **Try the agent**: a free-text box for a treatment question, an off-topic prompt, a note with an injected instruction, or
  your own text. Every send is a single request; nothing is remembered.
- **Model card**: the classifier's model card, with a check that it describes the model that is running.
- **About this project**: the project description, shown from `content/about.md`.

**Writing the About text.** Edit `content/about.md` like any markdown file (headings, lists, tables and links all render; images do not, and links open in a new tab). It starts as an outline: each section has a draft paragraph that begins `*Suggested content:*`. Replace a paragraph with your own text and delete the marker; `grep -n 'Suggested content' content/about.md` lists the sections still unwritten. Take any figures from `evals/README.md` and the result files, not from memory, so they stay checkable.

## How a request travels

```
browser --> /api/analyze (this app's server route) --> agent service (Vercel, Python) --> Claude Haiku 5.5
              adds the shared secret and the                 guards, scoring tool, reply check
              visitor address, returns a whitelist           counters in a shared store (Upstash Redis)
```

The browser never holds the shared secret or the agent's address (`AGENT_URL` has no `NEXT_PUBLIC_` prefix). A Playwright test
builds the app and searches everything sent to the browser for both.

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
`uv run evals demo-patients` (from `evals/`) writes `demo_patients.json`; `uv run training card` (from `training/`) refreshes
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

**Telling people apart.** Give each recipient their own link with a `ref`, for example `https://vk-web-liart.vercel.app/?ref=ode`,
and filter by `ref` in PostHog. The page cannot tell which company a visitor works at; the link is the only way.

**PostHog project settings (do these once).**
1. Project Settings, Web Analytics: turn on **Cookieless server hash mode**. Without it PostHog ignores cookieless events, and the
   page counts nothing.
2. Authorized URLs: only the production address.
3. Leave session replay off. Cookieless unique visitors are approximate (a hash of address and browser that changes daily).

`deploy/check-env.sh <agent-project> <web-project>` also fails if the web project's preview environment holds the key.

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
| The demo page | https://vk-web-liart.vercel.app | `vk-web` (Root Directory `web/`) |
| The agent service | https://vk-agent-spike.vercel.app | `vk-agent-spike` (Root Directory: the repository root; the name is left from the spike) |

First deployed and checked on 2026-10-27: the agent reports Haiku 5.5 and the committed model hash `414c2d467c87…`; `uv run agent
smoke` passed against it (model hash, one scored request, one decline); `deploy/check-env.sh vk-agent-spike` passed; the page was
clicked through (four patients, the free-text examples, the model card and its hash check). The addresses are public; the
shared secret is what keeps the agent from being called around the page, and the daily cap and limits bound what a call can spend.

## What changes with real data

This page shows the framing, not an integration. In a real deployment the panel would live inside an existing EHR and read the
structured labs and notes already in the chart (through that system's own interfaces), the request would carry a verified
user and patient context, nothing would be pasted, and the risk model would be trained and validated on real data under the
rules that apply to it. None of that is built or claimed here.
