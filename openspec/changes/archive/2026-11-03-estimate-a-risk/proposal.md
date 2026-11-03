# Proposal

## Why

A visitor who skims the demo will not invent a clinical note, so today the free-text tab is used by almost nobody, and the guardrails (the injection and decline demos) are seen only through four canned messages. The model itself is a small logistic regression over eight labs and five symptoms, so moving one input and watching the estimate move is cheap, exact and instantly readable. A second scenario built on that gives a glance-level visitor something to do in seconds, and gives the guardrail demo a patient the visitor controls.

## What Changes

- Add a second scenario, **Estimate a risk**, beside the review queue. The nav becomes Review queue (default, still first), Estimate a risk, and Behind the demo (now the model card and About only). The page title becomes VK-Check, with a subtitle for each scenario; "Supervisor review" stays the queue's title.
- Estimate a risk shows eight lab sliders, each with a "not done" state, and five symptom toggles (absent, possible, present). It opens on a prepared borderline patient and has a Reset button. It never starts from a queue case, and nothing in the queue becomes editable.
- A live dial shows the estimate, its routing band and a breakdown bar for each input, from the classifier alone. No language model is called while a slider moves and no spend is incurred.
- A button sends the current patient to the assistant. The patient is turned into a note by a fixed template in `risk_model`, and the note goes through the existing guards, assistant, scoring tool and reply check. The page shows the assistant's number beside the dial's.
- Three guardrail buttons act on the current patient: add a hidden instruction to its note, ask for a treatment, and go off-topic. Each shows what the guards did.
- The free-text box stays, collapsed, inside this scenario. The "Try the assistant" tab is removed from Behind the demo.
- Add a stateless service route that returns the estimate, the breakdown and the generated note for a set of inputs, with the same rate limit as the other routes and no model call.

## Capabilities

### New Capabilities
- `risk-estimator`: the what-if scenario: the inputs and their limits, the live estimate and breakdown, the patient-to-note template and its round-trip guarantee, the guardrail actions, and the rule that it never edits a recorded value.

### Modified Capabilities
- `web-demo`: the shell is titled VK-Check with a per-scenario subtitle; the nav has two scenarios; Behind the demo holds the model card and About; the free-text view moves into Estimate a risk and is no longer reached from Behind the demo.
- `agent-service`: a new route that estimates from structured inputs without a model call.

## Impact

- `risk_model/` (an estimate function with breakdown and the note template, numpy only; no model files change, so the model hash and card stay valid), `agent/` (the new route, guards and caps for its inputs), `web/` (shell, scenario view, slider and toggle components, new server route), `evals/` (a round-trip check and a guard check on the generated note).
- **Reverses** a non-goal recorded in the archived `evidence-first-chart` and `pet-ct-readiness` changes ("sliders or any editing of recorded values"). The reversal is narrow: this scenario edits made-up inputs and never a recorded value; the queue's "nothing edits a recorded value" rule is unchanged.
- No new dependencies and no new secrets. The live dial costs nothing; only the explicit send to the assistant spends, under the existing caps.
- Out of scope: starting from a queue case, saving or sharing a patient, multi-turn state, a differential diagnosis, advice on which test to order, changes to training, the generator, the policy or the frozen evals.
- Eval categories affected: text-path agreement (the generated note must read back to the inputs), guard behaviour on the generated note with and without an injection, and no-advice (the dial and its labels contain no treatment wording).
