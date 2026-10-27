# Proposal

## Why

The agent service is safe and measured but nothing a visitor can open sits in front of it, and the project's link is meant to be opened cold by someone evaluating it. A clinician would not paste notes into a chatbot; they would be in a chart, with a decision-support panel that reads what is already there. The demo should show that framing while the guards and the evals stay the real subject. It must also be cheap and reliable to leave running: a public page that spends money needs spend and rate limits that actually hold when the platform runs several short-lived instances.

## What Changes

- Add the **web demo** (`web/`, Next.js): a mock patient chart with a "Run V-K check" button that sends the chart's contents (labs and note, built exactly as the eval harness builds a message) to the agent and shows the result in a report card beside the chart; a "message sent to the agent" expander; a second tab with a free-text box for trying treatment questions, out-of-scope prompts and injected addenda; and a tab that shows the classifier's model card and whether it describes the model that is running.
- Add a **server route** that is the only thing the browser talks to: it adds the shared secret and the visitor address, forwards to the agent, and returns only the fields the page shows, with clear messages for each of the service's error statuses.
- Add **3 to 4 demo patients** from the dev split, committed with their pre-rendered message, including one with a unit mismatch and a missing lab. They contain no ground-truth field; a test keeps the file equal to what the harness renders.
- **Deploy on Vercel only**, as the Python service (the agent) and the Next.js app, with no second host. A first task is a spike that measures whether Strands runs there, the bundle size and the cold start; if it fails, the design names the fallback (a container host) before more is built.
- Move the agent's **spend and rate-limit counters into an optional shared store** (a Redis-compatible store over HTTP, such as Upstash). The in-memory and SQLite versions remain for local runs and tests. In production the service refuses to start without the store, because per-instance counters would not enforce the daily dollar cap.
- Move the committed model card into the web app's content and add a freshness test, so the page shows the card in the repository.
- Document the environment variables, the Retry-After handling and a deployed smoke test; set a public daily cap and limits.

## Capabilities

### New Capabilities
- `web-demo`: the mock chart page, the message the check sends, the report card, the free-text tab, the model-card tab, the banners, the server route and its error handling, and what the browser is never given.
- `deployment`: the Vercel deployment of the web app and the agent service, the environment variables and where each secret lives, the public limits, the preview-environment rules and the deployed smoke test.

### Modified Capabilities
- `agent-service`: spend and rate-limit counters may live in a shared store so that the limits hold across instances and restarts, and production refuses to start without one.

## Impact

- New: `web/` (Next.js, Playwright tests), `web/content/` (demo patients, model card), a script in `evals/` that writes the demo patients, an ASGI entry point and a store module in `agent/`, Vercel project configuration.
- Changed: `agent/` (counters behind an interface, settings, README), `training/tests` (card copy is current), `AGENTS.md`, `evals/README.md`.
- Dependencies: Node packages for the web app (pinned); in `agent/`, none new (the store is spoken to over `httpx`, already a dependency).
- Services: a Vercel project (free tier) and an Upstash Redis database (free tier); `ANTHROPIC_API_KEY` set only in the Vercel production environment.
- No change to the model, its hash or any recorded result.
