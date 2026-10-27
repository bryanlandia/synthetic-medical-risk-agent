# Design

## Context

The agent service (`agent/`) is a FastAPI app that keeps two guards in the process: a sliding-window rate limiter in memory (`ratelimit.py`) and the day's dollar total in a SQLite file (`spend.py`). Both are correct on one long-lived process. The platform chosen for the demo is Vercel only, whose Python functions run as short-lived instances with an ephemeral filesystem, possibly several at once, so neither guard would enforce anything there. The first live runs also showed that a Strands call runs on its own event loop and that the model client is built per request; both carry over.

Facts about the service the page depends on, observed in the code: `/healthz` returns the model hash without calling a model; `/analyze` returns `declined`, `decline_reason`, `reply`, `reply_source`, `report` (probability, uncertain, symptoms, labs_used, data_quality, evidence, disclaimer) and `usage`; errors are 401, 413, 422, 429 (with `Retry-After`), 502 and 503; an authenticated caller may name a visitor in `x-visitor-address`. The evaluation harness builds a message in `evals/src/evals/messages.py` (`render_message`: a "Labs:" list, a blank line, a "Note:" section). The synthetic dataset's input view is the lab panel and the note, and the dev split is the 500 held-out records the repository already iterates on.

## Goals / Non-Goals

**Goals:** a page a stranger can understand in a minute; the guards and evals visible as the substance; spend that cannot exceed the cap whatever the traffic; one platform to operate; a secret that never reaches a browser.

**Non-Goals:** multi-turn chat, accounts, stored messages, any real EHR integration (a real deployment would embed in an existing EHR and pull structured values from it; the page may say so in one sentence), design polish beyond one chart page and a few tabs, and changes to the model, the prompt or any recorded result.

## Decisions

**1. Vercel only, decided by a spike.** The agent's installed dependencies are about 126 MB (botocore 27 MB, numpy 24 MB, anthropic 14 MB, Strands 6 MB) and the model files are 228 kB, against a documented Python function limit of 500 MB uncompressed; a request takes about 4 s against a duration limit of minutes on Fluid compute. These come from the platform's documentation and are checked, not assumed: task 1 deploys the real service and records (a) that Strands imports and runs, (b) the deployed bundle size, (c) the cold-start time, (d) whether the Python code outside `web/` can be included, and (e) the sticking points of one project against two. The two layouts:

```
A. one project, root web/               B. two projects, one repo
   web/app/...   (Next.js)                 web/    root dir web/   (Next.js)
   web/api/*.py  (Python function)         agent/  root dir agent/ (Python function)
   imports ../agent, ../risk_model         web calls AGENT_URL (server side only)
```

B keeps the agent's dependencies and bundle separate and needs no cross-root includes beyond `risk_model` and the model files; A has one URL and one deploy. The spike picks; this design does not. If the service does not run within the limits, work stops and the design is amended to a container host (the agent code is unchanged; the store below makes that move safe) before the page is built. Alternatives rejected: rewriting the agent in TypeScript (breaks the Python-for-everything rule, drops Strands, would need every eval redone for parity).

**2. A shared store for the counters, behind two small interfaces.** `SpendCounter` and `RateLimiter` become interfaces with the present implementations (SQLite, in memory) kept for local runs and tests, and Redis-over-HTTP implementations added (Upstash's REST API, spoken to with `httpx`, which the service already depends on, so no new Python dependency). Spend: `GET` the day's key before the call and `INCRBYFLOAT` after, key `spend:YYYY-MM-DD` (UTC) with a two-day expiry. Rate: fixed windows, `INCR` on `rate:min:<client>:<minute>` (expiry 60 s) and `rate:day:<client>:<day>`; `Retry-After` is the seconds to the end of the window. Settings: `AGENT_STORE_URL` and `AGENT_STORE_TOKEN`; in production the service refuses to start without them. Two differences from the present code, both small and stated in the README: fixed windows allow up to twice the per-minute limit across a window boundary, and concurrent requests can overshoot the daily cap by at most (concurrency x one request's cost, about $0.0006), as the SQLite version already can. Alternatives: Vercel's own key-value product (the same shape, a different vendor name; Upstash is what the Marketplace provides); a paid persistent disk (needs a different host).

**3. The ASGI entry point.** `agent/src/agent/asgi.py` exposes `app = create_app(...)` built from the environment, with the real or scripted orchestrator by settings, so Vercel, `uvicorn` and the tests all import the same object. `agent serve` keeps working.

**4. The server route is the whole API surface of the web app.** `web/app/api/analyze/route.ts` reads `{message}`, rejects anything else, takes the visitor address from the platform's forwarded-for header (the platform sets it; the browser cannot), adds `x-shared-secret` and `x-visitor-address`, forwards to `AGENT_URL` with a timeout shorter than the function's, and returns a whitelist of fields (`declined`, `decline_reason`, `reply`, `reply_source`, `report`, and `usage` totals) or a mapped error. It never forwards an upstream body it did not parse. `/api/health` returns the agent's model hash for the model-card tab. `AGENT_URL` and `AGENT_SHARED_SECRET` are server-only variables (no `NEXT_PUBLIC_` prefix). In layout A the route may call the function by path; the secret still applies because the function is publicly reachable.

**5. Demo patients are pre-rendered by the harness, not reimplemented.** A command in `evals/` (`evals demo-patients`) picks the demo patients from the dev split by fixed rules (the first dev record, in id order, with each of: no data problem; a unit mismatch together with a missing lab; a borderline probability; a contradiction), renders each with `render_message`, and writes `web/content/demo_patients.json` with the chart (labs with name and unit, the note), the message string and the patient id and split. No ground-truth field is written. The page displays the chart from the structure and posts the stored message, so there is no TypeScript rendering to keep in step. Tests (in `evals/`): ids are dev, messages equal a fresh render, no ground-truth key, file equals what the command writes.

**6. The model-card tab.** The card is copied to `web/content/model-card.md` by a command and a test in `training/` fails if the copy differs from `training/model/MODEL_CARD.md`. The page splits off the metadata block, renders the body as GitHub-flavored markdown, and compares the hash on its "Model hash" line with `/api/health`. A mismatch shows a warning, not an error: it is information.

**7. Limits for a public link.** Daily cap $1 (about 1,600 requests at the measured $0.0006); per visitor 10 per minute and 200 per day (the service's defaults); `AGENT_ENV=production`; the API key only in the production environment; previews run the scripted model (the service allows it outside production), so a preview URL cannot spend money. One chart check is one request.

**8. Tests.** Playwright against a local Next.js server and the local agent started with the scripted model (no key, no spend), covering: the chart flow and the card, the expander equals the request body, the unit-mismatch patient's warnings, free text declined, 429 and 503 messages (the scripted service started with a tiny limit and cap), and that the production build's client files contain neither the secret nor the agent URL. Python unit tests cover the Redis implementations against a fake store over `httpx`'s mock transport, the two-instances-share-a-cap behavior, and production refusing to start without a store. A deployed smoke test (`agent` CLI or a script) is run by the owner against the real deployment: health hash, one scored request, one decline.

**9. Errors.** One mapping table in the route; the page shows the mapped message and, for 429, the wait from `Retry-After`. The page never shows an upstream body, a stack trace or the secret.

## Risks / Trade-offs

- **Strands or a dependency may not run on the platform**, or the cold start may be slow. The spike is first, and the fallback host is a design amendment, not a rewrite.
- **Cold start adds to the first request** (a few seconds on top of the model's 4). The page shows a "working" state and the route's timeout allows for it.
- **Fixed-window rate limits** are looser than sliding windows at a boundary; the daily dollar cap remains the real bound.
- **Hobby plan terms.** The free plan is for non-commercial use; a portfolio demo fits, and the README says so.
- **A visitor can still try anything in the free-text tab.** That is the point: the guards and the measured scope results are the substance, and the cap bounds the cost.
- **The page can be reached directly at the Python function's URL.** The shared secret and the limits apply to direct calls the same way.
- **Two copies of the card and the patients** (in `web/content/`) can go stale; the tests make staleness a failing build.

## Open Questions

- Layout A or B: decided by the spike (Decision 1), not by the owner.
