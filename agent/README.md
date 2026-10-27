# agent

Chat service in front of the risk classifier for a **FICTIONAL** disease (Velorin-Kessler syndrome). All data is synthetic;
nothing here is medical advice. A person pastes invented labs and a note as free text; a Strands agent (Claude Haiku 5.5)
decides whether to score it; the classifier's report comes back unchanged with a short plain-language reply.

## How a request is handled

```
POST /analyze  {"message": "<free text>"}
   1. shared secret            (401)   constant-time compare, before anything is read
   2. size and shape           (413, 422)   6,000 characters; control characters removed
   3. rate limit               (429)   10 a minute and 200 a day per client, Retry-After
   4. daily spend              (503)   a dollar cap that survives a restart
   5. the agent: ONE of two tools, at most two model turns
        score_message()   no arguments: scores the user's exact message (labs read by pattern, then the classifier)
        decline(reason)   out_of_scope | treatment_request | real_disease | phi | other
   6. reply check          the model's reply is released only if its numbers match the report and it holds no
                           medication, dose, treatment or real-disease content; otherwise a template from the report is used
   7. the disclaimer and the synthetic-data notice are appended by code
```

The model never types a number: the scoring tool reads the message from request state the model cannot set, so what is scored
is what the user wrote. A message the model does not route to a tool becomes an out-of-scope decline with a fixed message,
never the model's own prose. Nothing from the message, the reply, the secret or the key is logged.

Response: `request_id`, `declined`, `decline_reason`, `reply`, `reply_source` (`model` or `template`), `report` (the risk report,
or null) and `usage` (tokens, `cost_usd`, `tool_calls`, `model_calls`). `GET /healthz` returns the model hash, the model id and
the prompt hash.

## Configuration (environment variables only)

| Variable | Meaning | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | the key; never in a file | required unless the scripted model is on |
| `AGENT_SHARED_SECRET` | the secret the web proxy sends in `X-Shared-Secret` | required (or `AGENT_LOCAL_DEV=1`) |
| `AGENT_ENV` | `development`, `test` or `production` | `development` |
| `AGENT_DAILY_BUDGET_USD` | daily dollar cap | `2.0` |
| `AGENT_RATE_PER_MINUTE`, `AGENT_RATE_PER_DAY` | per-client limits | `10`, `200` |
| `AGENT_MAX_MESSAGE_CHARS`, `AGENT_MAX_TOKENS` | input cap, tokens per model call (thinking shares them) | `6000`, `2000` |
| `AGENT_EFFORT` | thinking effort of the model: `low`, `medium` or `high` | `low` |
| `AGENT_SPEND_DB` | the SQLite file that holds the day's spend | `spend.db` |
| `AGENT_MODEL_ID` | the orchestrator model (must have a pinned price) | `claude-haiku-5-5` |
| `RISK_MODEL_DIR` | the classifier's model files | `training/model` |
| `AGENT_SCRIPTED_MODEL`, `AGENT_RELAX_LIMITS`, `AGENT_LOCAL_DEV` | test switches; refused when `AGENT_ENV=production` | off |

The service refuses to start on a bad configuration and names the variable, never its value. A request from a caller that
presented the secret may name the visitor it acts for in `X-Visitor-Address`, and the rate limit uses that; an unauthenticated
request never reaches the limiter. The rate limiter is in memory, so it assumes **one instance**.

## Run it

From `agent/` (`UV_PYTHON_PREFERENCE=only-managed PATH=$HOME/.local/bin:$PATH uv ...`):

```
uv sync
uv run pytest -q                                    # no key, no network

# locally with the scripted model (free, deterministic):
AGENT_SCRIPTED_MODEL=1 AGENT_LOCAL_DEV=1 uv run agent serve
curl -s localhost:8000/analyze -H 'content-type: application/json' \
  -d '{"message": "Velorin index 128 mg/dL, serum K-17 3.6 mmol/L. The patient reports tremor."}'

# with the real model (spends money; export the key in your own shell):
AGENT_SHARED_SECRET=<a secret> uv run agent serve
uv run agent live-check                             # 5 hand-picked messages through the real model, a few cents
```

## Evals (from `evals/`)

`uv run evals estimate --system agent` (no key), `uv run evals run --system agent --split dev` (starts the service itself with the
scripted model; add `--live --yes` for the real one, or `--base-url` for a running service), `uv run evals agent-scope` for the
66-prompt scope set, then `test` and `adversarial` with `--final` once each. A live run sets the service's own daily cap to the
stage cap. The guard tests also run inside `uv run evals regression`.

## Layout

`src/agent/`: `config` (fail-closed settings), `app` (the endpoint and the ordered checks), `ratelimit`, `spend` and `pricing`,
`tools` and `runtime` (the Strands agent), `scripted` (the test model), `guard` and `replies` (the reply check, the template and
the fixed declines), `logs`, `prompts/system.md`, `denylist.json` (kept at least as strict as the evals' content check by a test).
