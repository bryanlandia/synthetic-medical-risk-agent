## 1. Spike: can the service run on Vercel

- [x] 1.1 Deploy the real agent service (scripted model first) to a throwaway Vercel project from this branch, with the model files and `risk_model` included, and record in the design: whether Strands and the FastAPI app import and answer `/healthz` and a scripted `/analyze`, the deployed bundle size, the cold-start and warm times, and how the code outside the project's root directory was included. Eval: the three numbers and the include method are written into the design's Decision 1.
- [x] 1.2 Choose layout A or B from the results and write the choice and the reason into the design. If the service does not run within the platform's limits, STOP and amend the design to name the replacement host; do not continue to group 2 without the owner's agreement.

## 2. A shared store for the counters

- [x] 2.1 Put `SpendCounter` and `RateLimiter` behind interfaces, keep the SQLite and in-memory implementations, and add Redis-over-HTTP implementations with the keys and expiries in Decision 2. Eval: the existing guard tests pass unchanged against the local implementations.
- [x] 2.2 Add `AGENT_STORE_URL` and `AGENT_STORE_TOKEN` to the settings, select the store when set, and refuse to start in production without it, naming the variable and not its value; also accept `AGENT_ENV=preview` (treated like development: the scripted model is allowed). Eval: tests for the selection and for the production refusal.
- [x] 2.3 Test the Redis implementations against a fake store (httpx mock transport): two instances sharing one daily cap and one visitor limit, the day rollover, `Retry-After` from the window end, and that a store error fails closed (the request is refused, not served). Eval: those scenarios pass.
- [x] 2.4 Make `agent serve` use `agent/src/agent/asgi.py` (added by the spike) and keep the repository-root `index.py`, `requirements.txt`, `vercel.json` and `.vercelignore`. Eval: the existing service tests import the same app object, and a test fails if the pins in the root `requirements.txt` differ from `agent/pyproject.toml`.

## 3. Demo patients and the model-card copy

- [x] 3.1 Add `evals demo-patients`: choose the demo patients from the dev split by the rules in Decision 5, render each with `render_message`, and write `web/content/demo_patients.json` with chart, message, patient id and split and no ground-truth field. Eval: tests that every id is dev, every message equals a fresh render, no ground-truth key is present, and the committed file equals the command's output.
- [x] 3.2 Add the model-card copy command and the freshness test in `training/` (the copy in `web/content/model-card.md` equals `training/model/MODEL_CARD.md`). Eval: the test fails when the copy is edited.

## 4. The web app

- [x] 4.1 Create the Next.js app in `web/` (TypeScript, pinned dependencies, no analytics or third-party scripts), the banner and the mock-EHR label on every screen, and the layout of the chart page and tabs. Eval: the banner and the label are visible on each tab in a Playwright test.
- [x] 4.2 Implement the server route `/api/analyze` and `/api/health` as in Decision 4, with the error mapping of Decision 9. Eval: unit tests of the route against a fake service for each status (200 scored, 200 declined, 401, 413, 422, 429 with `Retry-After`, 502, 503, timeout) and that the response carries only the whitelisted fields.
- [x] 4.3 Implement the chart page: patient selector, chart, "Run V-K check", the "message sent" expander and the report card for scored and declined results, and the working state. Eval: Playwright against the scripted service: the request body equals the expander text; the unit-mismatch patient shows both warnings; the card shows the disclaimer.
- [x] 4.4 Implement the free-text tab (one message per send, nothing kept) and the model-card tab (rendered body, hash comparison). Eval: Playwright: a treatment question shows a decline and no probability; two sends keep no history; matching and mismatching hashes show the match and the warning.
- [x] 4.5 Check the production build: neither the shared secret nor the agent address appears in any browser-visible file. Eval: a test that builds, then searches the client output for both values and fails if either is found.

## 5. Deploy

- [x] 5.1 Configure the Vercel project(s) as chosen in 1.2: production holds the API key, secret, store credentials, `AGENT_ENV=production`, the $1 daily cap and the limits; previews use the scripted model and no key. Write the environment-variable table and the `Retry-After` guidance in the READMEs. Eval: the table lists every variable with its purpose; a script checks a preview's configuration has no key (owner-run).
- [x] 5.2 Add the deployed smoke test (health hash equals the committed manifest hash, one scored request returns a report, one treatment request is declined) as a documented command. Eval: it passes against a local scripted service, and the owner runs it against the deployment.
- [x] 5.3 Owner-run: deploy, run the smoke test, open the page, run each demo patient and one free-text decline. Record the outcome and the deployed URL in the README (the URL goes in the README, never in client code).

## 6. Documentation and validation

- [x] 6.1 Update `AGENTS.md` (layout and commands for `web/`, the store variables, the demo-patients and card-copy commands), `web/README.md`, `agent/README.md` (the store, the entry point, the limits) and `evals/README.md` (the demo patients). Include a short "what changes with real data" paragraph in `web/README.md`.
- [x] 6.2 Run the full suites for `risk_model/`, `agent/`, `training/` and `evals/`, the fast regression, the web unit tests and Playwright tests, and `openspec validate add-web-demo --strict`.
