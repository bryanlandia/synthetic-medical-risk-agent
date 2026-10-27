# Proposal

## Why

The classifier beats the frontier baseline on the shared evals and runs in under a millisecond on a CPU, but nothing a visitor can use sits in front of it. The project's demo is a chat agent: a person pastes a fictional patient's labs and note, and an assistant scores the record and explains the result in plain language, without ever giving medical advice. That needs an LLM orchestrator, and an LLM in front of a public endpoint brings three new risks the evals do not yet cover: it can mis-transcribe the numbers it passes on, it can be talked into out-of-scope or unsafe answers, and anyone can spend the project's money. This change builds the agent service with those risks closed by design and measured by evals, so the web page and the deployment (the next change) have a safe thing to call.

## What Changes

- Add **text intake**: deterministic code that turns one free-text message into the record view the classifier reads (a lab panel and a note). Lab values come from the values the message states, read by pattern, never from a model.
- Add the **agent service**: a FastAPI app with one chat endpoint and a health check, and a Strands agent (Claude Haiku 5.5 through the Anthropic API) with one tool, `score_message`. The tool takes **no value arguments**: the service gives it the user's exact message through request state the model does not control, so the model decides whether to score but never what is scored. The tool returns the classifier's report unchanged.
- Add **guards in code around the model**: a shared-secret header, an input size cap, a per-client rate limit, a per-request token cap, a **daily dollar cap** that stops calls to the model when reached, a limit of one tool call per request, and an **output guard** that checks the reply against the report (quoted numbers match, the disclaimer is present, no treatment or real-disease content) and replaces a failing reply with a templated summary built from the report.
- Make the assistant **decline** treatment requests, questions about real diseases, personal-data-looking input and other out-of-scope chat, with a fixed refusal shape, and ignore instructions inside the pasted text.
- Add an **agent system to the evals**: the harness renders each record as a message, calls the running service over HTTP and grades the returned report with the existing graders, so the agent is scored on the same categories as the classifier and the frontier baseline, plus new **tool-use and scope checks** from a small committed prompt set (tool called once when it should be, not called when it should not be, refusals, over-refusal of legitimate notes, reply numbers equal to the report, guard behavior).
- Split the inference package into its own small project (`risk_model/`, numpy only) so the service image does not carry scikit-learn or MLflow. This is a behavior-preserving move: the model hash and every existing test result are unchanged.
- Record each request without the message text (request id, sizes, tool calls, tokens, cost, latency) in structured logs.

## Capabilities

### New Capabilities
- `text-intake`: turning a free-text message into a record view deterministically, how repeated, missing, alternate-unit and impossible values are handled, and what the intake guarantees about the values it passes on.
- `agent-service`: the chat endpoint and its contract, the scoring tool, the guards (authentication, size, rate, token and spend limits, one tool call), the output guard and its fallback, the refusal behavior, and the logging and configuration rules.

### Modified Capabilities
- `eval-harness`: added requirements for scoring the agent through its HTTP interface on the existing graders, and for the tool-use and scope checks (tool-call correctness, refusals and over-refusal, reply consistency with the report, guard behavior).

## Out of scope

- The web page, the Vercel proxy and the Render deployment, and a container image (the next change). The service runs locally and in CI.
- Conversation memory: each request is one message and the service keeps no history.
- Accepting a structured record (JSON) from clients; the only input is free text.
- The LoRA model, any change to the classifier or the note reader, and any change to the report contract.
- Authentication beyond the shared secret, user accounts, and storing any request.
- The wider safety and scope dataset (a larger red-team set); this change commits a small prompt set sized to its own checks.

## Eval categories affected

Every existing category gets an `agent` row (happy path, symptom reading, data quality, borderline, consistency, adversarial and the fabrication, safety and parse checks), and a new tool-use and scope category is added with its own targets. The difference between the agent and the classifier alone is what the orchestrator and the text intake add or cost.

## Impact

- New `agent/` project (Python 3.12, uv, pinned `strands-agents[anthropic]`, FastAPI, uvicorn); a new `risk_model/` project holding the inference package moved out of `training/` (`training` and `agent` depend on it); `evals/` gains an `agent` system, a prompt set under `evals/datasets/`, tool-use graders and a service-launching helper.
- Spend: the live evals use Haiku 5.5 through the owner's key. The keyless `evals estimate --system agent` gives about $0.35 for a dev run of 500 records, about $1 for `test`, $0.30 for `adversarial`, $1.40 for the three-trial stage and a few cents for the scope set (about $3 in all, on assumed token counts that the live dev run replaces). The service's own daily cap is configured per environment and is switched up for eval runs. Unit tests and CI use a scripted model and spend nothing.
- Secrets: `ANTHROPIC_API_KEY` and the shared secret are read from the environment only; nothing is stored in a file, a log or client code, and the service's URL appears in no client code.
- Reproducibility: the intake, the classifier and the output guard are deterministic; the only nondeterminism is the orchestrator's wording, and the reply is checked against the report either way.
