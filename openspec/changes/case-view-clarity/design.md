# Design

## Context

Everything here is in `web/` plus one field in `evals/src/evals/demo_cases.py` (`received` is `"HH:MM"` between 07:30 and 16:45, one working day). The chart is `CaseView.tsx` (`Chart`, `PreparerAnswers`, `Checklist`, `PacketBody`), the released packet `ReleasedPacket.tsx`, and the words live in `web/lib/copy.ts` (`DEMO_NOTES`, `HINTS`, `PURPOSE_*`). Each criterion in the policy copy has a `source` of `lab`, `note` or `attestation`; the packet carries `summary_source` (`model` or `template`) and the risk report.

## Goals / Non-Goals

**Goals:** fix the six wording and control problems; make it plain, at a glance, what each part of the page was produced by.
**Non-Goals:** changing what any model or rule does; changing the agent's output; adding analytics events.

## Decisions

- **Provenance is one component and one table.** `Produced` (a small chip plus a hover/focus hint) takes a kind from a single table in `copy.ts`: `classifier` ("Classifier model": a small model trained on invented data), `reader` ("Note reader": a small model that reads the clinical note), `rules` ("Code": fixed rules and checks, no model), `llm` ("Language model": Claude Haiku drafts, code checks each sentence), `template` ("Template": fixed text, no model), `preparer` ("Preparer, simulated") and `you`. The key text is built from the same table, so chips and key cannot drift. Kinds are names of roles, not claims about accuracy; no figures.
- **Chips go where the thing is shown:** the estimate (`classifier`), the checklist and its statuses (`rules`), with the note reader named on the criterion that comes from the note (the label sits on the C2 row's Source cell, not on the note itself, which the reader reads but does not write), the answers (`preparer`), the summary (`llm` or `template` from `summary_source`), the decision area (`you`), and in the released packet beside the checklist, the summary and the rationale. The checklist's new Source column maps from the policy: `lab` rows say "Chart labs, rules", `note` rows "Clinical note, note reader and rules", `attestation` rows "Preparer's answer". Assumption: C2's evidence also comes through the note reader, which is true of the pipeline today (`risk_model`'s reader), so naming it is accurate.
- **The key is a dialog, not a banner.** "What produced this page?" opens from the case header and the queue header (counted by the existing `help` name) with the same Escape and focus-return behavior as the help dialog; on the free-text view one sentence with labels names the guards (code), the agent and the classifier it calls. The key button reuses the existing `help` analytics name, so a case has two elements with it. Not dismissible-banner clutter, in line with the Demo notes rule.
- **Sent-message control:** keep the MUI accordion (already keyboard operable) but label it "Show the message sent to the service" / "Hide ...", with a visible chevron and an outlined, button-like summary; analytics name `sent_message_expander` unchanged.
- **The `criteria` hint goes away, the words change.** `HINTS` keeps three terms; headings and the explanation text say "coverage criteria". Other uses of the bare word "criteria" in decision text are left alone (not a hinted term anywhere). Assumption: the request to "remove the underline" means removing the hint, not just its styling.
- **`answers` Demo note removed.** The preparer answers keep the "(simulated)" heading and the `preparer` chip; the role note still says the preparers do not exist. Spec text drops the answers from the list of noted elements.
- **Received time.** The builder draws a working day (three fictional days in the first week of November 2026, skipping the weekend) and a minute from its seed stream, and writes `received` as `YYYY-MM-DD HH:MM` in fictional Eastern time; the page formats it as "2 Nov 2026, 07:45 ET" without using the visitor's zone (no `Intl` locale dependence beyond fixed month names). Same seed, same values; byte-identical rebuild. Changing the file changes its hash, so saved progress is discarded once.
- **Estimate wording is composed from numbers only** and keeps the "context only, decides no criterion" sentence; the existing percent formatting is reused.
- **Fictional-first:** every chip and key sentence says the data and disease are invented where it names a model, and none mentions accuracy, cost or savings (the existing wording test is extended to the new strings).

## Risks / Trade-offs

- [Chips clutter the case view] → one small chip per block, none on rows of tables except the Source column; the key holds the detail.
- [Naming the note reader as part of C2 overstates or understates what it does] → the key sentence is checked against the `risk_model` description when written; a test only checks that the chip appears, so the wording is a review point in the PR.
- [Regenerating `cases.json` invalidates visitors' saved progress] → expected and already specified; noted in the PR.
- [ET label implies the visitor is in that zone] → the date and time are marked fictional by the existing queue note ("Names and times are made up").
