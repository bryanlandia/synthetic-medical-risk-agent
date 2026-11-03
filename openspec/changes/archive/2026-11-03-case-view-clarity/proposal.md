# Proposal

## Why

Review of the live demo found places where a visitor cannot tell what they are looking at: the model estimate is a bare percentage with no subject, the "message sent" control does not look openable, the chart's note is just "Note", the queue's "received" time has no date or zone, "criteria" is an underlined hint on a word that needs none, and a Demo note beside the preparer's answers repeats what the heading already says. A larger gap: the page never makes clear which parts are produced by a model or an agent, which by plain code and which by a simulated person, although that is the point of the project.

## What Changes

- **The estimate says what it estimates.** "The model estimates 41%..." becomes "Estimated risk of Velorin-Kessler syndrome (fictional): 41%, or 41% to 50% if the missing results are obtained. Context only; it decides no criterion."
- **The preparer-answers Demo note is removed.** The heading already says "(simulated)", and the role note says the preparers do not exist.
- **"criteria" is plain text, written "coverage criteria".** The hint underline on that word is removed (PET-CT, prior authorization and packet keep theirs).
- **The sent-message control looks openable.** It becomes a labelled disclosure with a chevron: "Show the message sent to the service" / "Hide ...".
- **The chart's "Note" is headed "Clinical note".**
- **"Received" shows a date and a time zone**, for example "2 Nov 2026, 07:45 ET". The dates are fictional, seeded, and spread over three working days; the zone is fixed Eastern time, whatever the visitor's own zone.
- **Where models and code operate is shown.** Each block of the case view and of the released packet carries a small provenance chip saying what produced it: **Classifier model** (the risk estimate), **Note reader** (a small model that reads the note; used for C2 and the tremor and symptom findings), **Code** (the lab-threshold rules for C1, the status logic and the verifier), **Language model** (the summary draft, Claude Haiku, or **Template** when it fell back), **Preparer (simulated)** (C3 to C6 answers) and **You** (decisions). The checklist gains a "Source" column. One short "What produced this page?" key, from one source string, opens from the case and the queue and also names the guard and the agent on the free-text view.

## Capabilities

### Modified Capabilities
- `review-workspace`: the explanation panel's term hints, the queue's received time, the case view (estimate wording, clinical note heading, sent-message control), the Demo notes, a new requirement for provenance, and the cases data's received field.

## Impact

- `web/` (components, `lib/copy.ts`, tests, README); `evals/` (`demo_cases.py` writes the received timestamp with a date and zone; `web/content/cases.json` regenerated, so its hash changes and saved progress in a visitor's browser is discarded once, as the spec already provides).
- No change to the policy, the model, the agent service, the packet endpoint or prompt, or any frozen eval result. No model spend.
- Out of scope: reworking the model-written summary text or gap messages, new analytics events (the new key control uses the existing `help` name), changing real timestamps in the audit timeline (they stay the visitor's session times).
- Eval categories affected: none graded by the harness; web tests cover the wording and the provenance chips.
