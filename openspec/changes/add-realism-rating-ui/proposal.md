# Proposal

## Why

The realism gate in `add-llm-note-writer` asks a rater to fill in a markdown sheet by hand: 88 notes, six fields each. That is fine for the developer once, but it is not something to hand to a clinician, and the developer is not a clinician and cannot judge whether a note about a fictional syndrome reads like real documentation. The gate needs a rating tool a reviewer would actually use, and a way to get a credible, skeptical second opinion when no clinician is available. A recorded run of an LLM reviewer working through that same tool is also a concrete demo of an agent operating a real UI.

## What Changes

- Add a small local Next.js app (`rating_ui/`) that shows the blind pilot notes one at a time, lets a rater set plausibility and the five symptom labels with the keyboard or mouse, saves as they go, and can be resumed. It reads the blind sheet only; it never reads or serves the key.
- Add a machine-readable blind sheet (`sheet.json`) next to the markdown one, and a rating file format (`ratings.<rater>.json`) that records who rated, whether the rater is a `human` or an `llm`, and the labels.
- Teach `data-gen gate` to load those rating files. The gate states which kinds of rater it accepted, and by default accepts only `human` ratings. Accepting `llm` ratings is an explicit configuration choice that is recorded in the gate report and in the dataset manifest.
- Add an adversarial LLM reviewer: a different, stronger model (Sonnet 5.5, against the Haiku 5.5 writer) with a skeptical-clinician prompt, blind to settings and to the key. It runs in two modes: a direct mode that rates from note text, and a UI mode in which it operates the rating app through Playwright using a small fixed set of tools, with the session recorded as a video.
- Spend on the reviewer is capped and cached like the writer's, and it needs no key unless it is run.
- Document how a clinician uses the tool, and how the demo recording is made.

## Capabilities

### New Capabilities
- `realism-rating`: the blind rating app and its file formats, how ratings from different rater kinds feed the realism gate, and the adversarial LLM reviewer including the recorded UI session.

### Modified Capabilities

None yet. The gate's rater-kind behavior is specified here as new requirements because `add-llm-note-writer` (which owns `llm-note-writing`) is not archived. When it is, the gate requirement there should be reconciled with this change at archive time.

## Out of scope

- Hosting the rating app. It is local-only for now; a public, authenticated deployment (accounts, shared storage, its own deployment separate from `web/`) is deferred and may be revisited.
- Accounts, authentication or multi-user hosting. A rater is a name typed into the app.
- Clinical validation. A pass means notes read as plausible to the rater, not that they match real records. An LLM reviewer is a stand-in and is labelled as one everywhere.
- Rating the final dataset, training, agent and eval code.
- Changing the gate thresholds (80% plausible per setting, 95% extractor agreement).

## Eval categories affected

None directly. This guards the quality of the inputs that every category depends on, and it gives the project a documented, reproducible account of how note realism was judged.

## Impact

- New `rating_ui/` (Next.js, TypeScript, local only); `data_gen` gains an optional `review` extra (`anthropic`, `playwright`), a `review` command, and a gate that reads rating files. `AGENTS.md` layout and commands are updated.
- Estimated reviewer cost: about 88 notes of roughly 1,000 input tokens each, well under one dollar at Sonnet pricing even with the UI loop. Capped by configuration.
- Adds a second, nondeterministic artifact kind (LLM ratings and a video). They are recorded outputs, not reproducible from a seed, and are described as such.
