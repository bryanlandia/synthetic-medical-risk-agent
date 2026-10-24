# Design

## Context

The realism gate (`data_gen/src/data_gen/llm/gate.py`) parses a hand-filled `ratings.md` and joins it to `key.json` by note id. The pilot already writes a blind `sheet.md` and a separate key, and Haiku 5.5 writes the notes. `web/` is reserved for the public Vercel demo and AGENTS.md says Python is used everywhere except `web/`. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- A tool a clinician can use without touching files, that cannot leak the key.
- One rating-file contract that the app, the LLM reviewer and the gate all share, with the rater's kind recorded.
- An independent, skeptical reviewer, and a recorded session of it operating the real app.

**Non-Goals:**
- Hosting, accounts or concurrent raters on one file.
- Pixel-level "computer use". The reviewer gets named actions mapped to the app, which is more reliable and cheaper, and still operates the real UI.
- Making LLM ratings reproducible from a seed.

## Decisions

**1. A separate local app in `rating_ui/`, not inside `web/`.** `web/` is deployed to Vercel with a public URL, and this app reads unreleased notes from disk. Keeping it separate means the unreleased notes cannot be published by accident while the app is local-only, and a README line plus a test that the app has no deploy config enforces that for now. A later hosted version would be its own deployment with authentication and shared storage, not a route in `web/`. Alternative: a route inside `web/` guarded by an env flag. Rejected: one misconfiguration away from publishing the pilot notes and the rating files.

**2. Next.js with route handlers that touch only two kinds of file.** The app runs on `127.0.0.1`, reads `sheet.json` and reads and writes `ratings.<rater>.json` in a directory given by `REALISM_ROUND_DIR`. A path guard resolves every path and rejects anything but those names. The key is never read, so there is nothing to leak even through a bug. The rater kind comes from `RATER_KIND` at launch, not from the request. Alternative: a Python server (FastAPI) serving a static page. Simpler to share code with the gate but the user chose Next.js, and the UI will be a reviewable frontend artifact.

**3. Rating file is JSON, one file per rater, written atomically.** `ratings.<rater>.json` holds rater, kind, model id and prompt version for an LLM, and a map from note id to the six fields and a comment. The app writes via temp file and rename after every change. One file per rater avoids any concurrent write problem and makes disagreement analysis a simple join. `ratings.md` stays supported and is read as kind `human`, so nothing already filled is wasted.

**4. The gate takes accepted rater kinds from configuration, default `["human"]`.** The developer is not a clinician, so the first real gate may run on an LLM review, but that must be a visible, recorded decision and not the default. Config key `llm.gate_rater_kinds`. With several accepted raters the gate uses the pessimistic plausibility so that adding a reviewer can only make the gate stricter. Extractor agreement uses each accepted rater's symptom labels and takes the pooled agreement. The accepted kinds go into the gate report and the manifest. Alternative: an `--accept-llm` flag. Rejected: it would not travel into the manifest, and the manifest is where a reader looks.

**5. The reviewer is Sonnet 5.5 with an adversarial prompt, in two modes.**
- *Direct mode*: one API call per note (or batches of five) with the note text and the instructions, output JSON validated against the same six fields plus a reason for any `n`. Cached and capped through the existing gateway, so a rerun is free and deterministic-by-cache. This is the cheap, testable path and the one used to measure discrimination against the controls.
- *UI mode*: a tool-use loop where the model sees the page text (an accessibility snapshot, not pixels) and calls named tools: `read_note`, `set_plausible`, `set_symptom`, `add_comment`, `next_note`, `finish`. Each tool maps to a fixed Playwright action on test ids. Playwright records a video of the context. The loop has a step limit and the shared spend cap. The app, not the reviewer, writes the rating file, so UI mode exercises the real save path.
The prompt tells the reviewer to look for artifice (tidy phrasing no clinician would use, template residue, values listed in implausible ways, unnatural hedging) and to say what it checked, without access to anything beyond the text. Different model from the writer is enforced by a check at start. Alternative: a different vendor's model, which would be more independent but adds a key, a dependency and a second spending path; recorded as a possible later improvement.

**6. The reviewer lives in `data_gen/` (Python) as an optional `review` extra.** It reuses the gateway (cache, caps, rate-limit backoff) and the rating schema. `anthropic` is already a dependency; `playwright` is added only under the extra so the base install and CI stay light. Alternative: a TypeScript reviewer inside `rating_ui/`. Rejected: duplicates the caching and cap logic and breaks the "Python except `web/`" convention.

**7. Discrimination is checked, not assumed.** The pilot already mixes in eight template controls. A reviewer that rates everything plausible would pass the gate meaninglessly, so the report requires the controls to score at least 20 points below the LLM notes or flags the reviewer as non-discriminating. A flagged run does not pass the gate.

**8. The video is a demo artifact, recorded and not reproducible.** It is written to the round directory, is git-ignored by default, and a trimmed copy may be committed under a size limit (15 MB, `webm`). The run's ratings, session log (each tool call with its result, refused actions counted) and token spend are saved beside it. The README says plainly that the run is a recording, not a seeded result.

## Risks / Trade-offs

- [An LLM reviewer shares blind spots with the LLM writer, so "plausible" may mean "reads like LLM text"] → different and stronger model, adversarial prompt, controls that must be rated lower, and labelling as an LLM review everywhere. It does not replace a clinician and the docs say so.
- [UI mode is flaky: selectors drift, the model loops] → test ids on every control, a fixed tool set, step and spend limits, and an end-to-end test using a scripted fake model against the real app.
- [The keyboard flow is hard to get right and untested UIs rot] → Playwright tests drive the app with a scripted rater for the keyboard-only, resume and incomplete scenarios; the same tests run against a built app in CI.
- [Leaking the key through the app] → the app never reads it; a test requests every route and several traversal paths and scans responses for the key's contents.
- [Video size in the repo] → git-ignored by default; committing a trimmed one is a manual, size-checked choice.
- [Spend] → direct-mode estimate is well under a dollar; UI mode is capped and the estimate command covers both.
- [Reconciliation with `llm-note-writing`] → the gate's human-rating requirement there says "the project owner". This change adds the rater kinds as new requirements; at archive time of both changes the older requirement should be updated to refer to the accepted rater kinds.

## Open Questions

- Whether to batch five notes per direct-mode call. Cheaper and probably fine, but could let notes influence each other's ratings; the default is one note per call and this can be revisited when the cost is measured.
