# web

**All data is synthetic and the disease is fictional. Nothing here is medical advice.** A public demo page: a **mock EHR** chart
(not connected to any real system; no FHIR, no vendor software) with a decision-support panel that runs the risk check on what
is on the chart. The guards and the evals around the agent are the real subject; the page is how a visitor sees them work.

- **Patient chart**: pick one of four invented patients (from the dev split, with their messages pre-rendered by the eval
  harness), read the labs and note, open "Message sent to the agent" to see the exact text, and press "Run V-K check".
- **Try the agent**: a free-text box for a treatment question, an off-topic prompt, a note with an injected instruction, or
  your own text. Every send is a single request; nothing is remembered.
- **Model card**: the classifier's model card, with a check that it describes the model that is running.

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

## What changes with real data

This page shows the framing, not an integration. In a real deployment the panel would live inside an existing EHR and read the
structured labs and notes already in the chart (through that system's own interfaces), the request would carry a verified
user and patient context, nothing would be pasted, and the risk model would be trained and validated on real data under the
rules that apply to it. None of that is built or claimed here.
