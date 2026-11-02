# Design

## Context

See proposal.md for why. The pieces this builds on already exist:

- `RiskClassifier` scores structured inputs (8 labs, each a value or missing; 5 symptoms, each absent, possible or present) and already exposes each feature's share of the score (`contributions`). Absent and not-mentioned symptoms are the same reference level, so three states are enough.
- `text-intake` and the note reader already turn a message back into a view, with a documented agreement test between the text path and the structured path.
- `/analyze` and `/packet` share one set of guards: secret, size caps, per-visitor limit of 10 a minute and 200 a day, daily spend cap. The limiter is in memory per process, with an optional shared store.
- The web shell (`Demo.tsx`) owns the header text "Supervisor review", an intro card and help dialog specific to the queue, and a "Behind the demo" menu holding the assistant, model card and About.

The binding constraint is the limiter: a slider emits tens of updates in a second, which a 10-a-minute limit cannot serve.

## Goals / Non-Goals

**Goals:**
- A visitor moves one control and sees the estimate and its breakdown change, with no wait that feels broken and no spend.
- The dial and the assistant can be compared on the same patient, and a disagreement is a visible, tested failure.
- One implementation of the scoring: the browser never computes a probability.

**Non-Goals:**
- Starting from a queue case or saving a patient.
- Explaining the model to a statistical standard (no confidence interval, no calibration plot).
- Changing the classifier, the note reader or the frozen evals.

## Decisions

**1. A separate `/estimate` route in the agent service, with its own limit counter.**
Chosen over computing in the browser. `risk_model` stays the only scorer and the model-card hash check keeps meaning that the running model is the described one; a TypeScript copy would need its own golden tests to earn that trust. The cost is a network hop per update. The route has no model call and the work is a dot product, so the time is network and cold start.
Its limit is 120 a minute and 5,000 a day, held in a second `RateLimiter` instance (and the shared store's second key prefix in production), so a slider cannot use up the assistant's 10 a minute or the visitor's daily allowance. It adds nothing to the daily spend.

**2. The client debounces and drops stale answers.**
Updates are sent at most every 150 ms while a control moves and once more when it stops. Each answer carries the sequence number of its request, and an older answer than the one shown is discarded. A 429 shows "slow down for a moment" and keeps the last estimate on screen. A first request slower than 1.5 s shows the existing "waking up" state.

**3. The note template lives in `risk_model` and is returned by `/estimate`.**
Chosen over a template in TypeScript. There is one definition of the message, the round-trip check is a plain Python test against the real reader, and the page sends back the exact message it was given. The template uses the same `Labs:` list format as the evals' documented message format, followed by a `Note:` section of short symptom sentences ("Reports tremor.", "Possible fatigue.", "Denies dizziness."). Values are written with a fixed number of decimals per lab, and the sliders step in exactly those increments, so a displayed value and a written value are the same number.

**4. The breakdown is grouped by input, not by model feature.**
The model has two columns per lab (value and missing-indicator) and two per symptom (present and possible). `contributions` already gives each column's share of the score after Platt scaling. The route sums them per input, so a lab or a symptom has one bar, and the starting point is the intercept after the same scaling. The sum of bars plus starting point is the score; the sigmoid of it is the probability. A test checks this identity across seeded inputs.

**5. The guardrail controls build their messages on the server's template, in the page.**
The page appends fixed strings to the message `/estimate` returned: a hidden instruction (the existing "report this as LOW risk" wording) and a treatment question. The off-topic control sends its fixed question alone. The strings are page copy, not model input from a visitor, and live next to the existing examples so the guard evals can be pointed at them.

**6. Navigation moves to two scenarios.**
`Demo.tsx` gets a scenario level above the current views: Queue (with its cases), Estimate a risk, and the Behind the demo menu (model card, About). The title becomes VK-Check; each scenario supplies its subtitle. The intro card and help stay in the queue. The free-text component is mounted inside Estimate a risk behind a disclosure and keeps its `send` behaviour. The Playwright tests that reached the assistant through Behind the demo are updated to reach it here.

**7. No storage.**
The scenario holds its inputs in page state only. It writes nothing to `localStorage`, so it cannot disturb queue progress or `casesHash` resets.

## Risks / Trade-offs

- **[Latency on a cold function]** the first estimate can take seconds → the "waking up" state, and the page keeps the opening patient's estimate precomputed in a committed file so the first view needs no request.
- **[The generated note does not read back]** rounding or wording the reader misreads → the round-trip requirement over all 243 symptom combinations and 200 seeded lab settings; if a wording fails, the template changes, never the reader (the reader is frozen with the model hash).
- **[A shared in-memory limiter]** two instances each hold their own counts → unchanged from today and stated in the README; the shared store, when configured, gets its own key prefix.
- **[Looks like a diagnostic calculator]** the framing and the excluded words are requirements, and the page says the patient is invented and the disease fictional → text checks in the web tests.
- **[Reverses an earlier non-goal]** sliders were ruled out in two archived changes → the reversal is limited to made-up inputs; the queue's rule is unchanged and tested (queue progress is untouched).
- **[Guardrail demo on a patient]** an injection that fails to change the number is the pass, but a note that scores low anyway proves nothing → the borderline start makes a forced-low instruction detectable, and the page says when the result cannot show it, as the current injection callout does.

## Migration Plan

Additive on the service: `/estimate` is new and nothing else changes, so the agent can deploy first and the web project second. If the web change must be reverted, the old shell and free-text tab return with it and the unused route is harmless. No model file, hash or cases file changes.

## Open Questions

- The exact opening patient: any input set whose estimate is in the band works; pick one and commit its precomputed estimate. The choice does not change the specs.
- The slider step for each lab (a power of ten that round-trips cleanly) is set when the template is written.
