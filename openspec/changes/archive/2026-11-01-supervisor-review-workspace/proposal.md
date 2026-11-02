# Proposal

## Why

The demo is organised around the tool, not around a person's work: four tabs, four hand-picked patients, and a PET-CT packet bolted under the chart. A visitor cannot tell what the packet is for, who would use it or what happens next. The real process is a worklist: someone prepares each request for an expensive scan, and a neurology supervisor reviews and releases it. Policy v2 (C1 met for 33 of 500 dev patients) now gives the demo enough cases where the checklist is actually met. This change rebuilds the web app around that worklist, explains plainly what the packet is for, and gives it a polished, friendly Material design.

## What Changes

- The visitor is a neurology supervisor with a **queue of 30 prepared cases**. The preparing clinicians are simulated and labelled as such. Statuses: New, In review, Returned, Released, Closed.
- **Explaining the packet.** The queue opens with a short "What is this packet for?" panel in plain words (the scan is expensive, so insurers ask for documentation first; an incomplete or uncited request is sent back, which delays the patient and creates rework; the tool assembles the packet, checks the chart against the insurer's fictional criteria, shows the evidence and lists what is missing; the supervisor decides; the tool decides nothing about care or coverage). The same text is a help dialog on every case, and PET-CT, prior authorization, packet and criteria have short hints where they first appear.
- **Opening a case** shows the chart (labs with reference ranges and flags, the note, the exact message sent) beside the packet: the criteria checklist with evidence and gaps, the checked summary, the model's estimate as context, and the preparing clinician's four answers (simulated). One packet request is made on first open and kept in the browser, so reopening costs nothing.
- **Three decisions:** Release (disabled while any criterion is unknown; needs the supervisor's own written rationale when any is unmet), Return with a note (the case shows a Returned chip and keeps the note), and Close, criteria not met. A Returned case can be reopened to In review (its note is kept and a Reopened event is added). Nothing is transmitted anywhere.
- A **released packet** is a cover sheet (fictional insurer, fictional request code, patient id, requested study), the checklist with evidence, the summary, the supervisor's rationale in their own words, and an audit timeline, with copy and print.
- **Progress is kept in `localStorage`** (returned cases and their notes survive a reload) with a Reset demo button that restores all 30 cases.
- **Demo notes** are quiet: one small "Demo" chip with muted text beside each simulated thing, plus one persistent top strip. The free-text assistant, the model card and About move under "Behind the demo".
- **Data:** a committed file of 30 cases drawn from the dev split by a seeded rule (8 to 10 with C1 met, 6 to 7 unknown, the rest unmet, with unit mismatch, contradiction, borderline and missing-lab cases), with seeded preparer answers (mostly complete, some unanswered, some "no"), one of ten fictional insurers, a fictional preparer name and received time per case. No ground truth in the file.
- **Design system:** Material UI (MUI) with a custom theme, no new fonts fetched from another site.
- Analytics click names change to a new fixed set; the privacy rules are unchanged and the supervisor's comments and rationale are never collected.

## Capabilities

### New Capabilities
- `review-workspace`: the explanation of what the packet is for, the queue, the case view, the three decisions, the released packet, persistence and reset, demo notes, and the cases data.

### Modified Capabilities
- `web-demo`: the chart-and-tabs page, the sample-patient file and the bolted-on packet panel are replaced; the free-text assistant, model card and About become views under "Behind the demo".
- `usage-analytics`: the fixed set of click names and the labels events may carry.

## Impact

- `web/` (almost every component, styles, content, tests, README), `evals/` (the demo-case builder replaces the demo-patient builder, with a stale-file test), `web/content/` (a cases file in place of `demo_patients.json`). New pinned web dependencies: `@mui/material`, `@emotion/react`, `@emotion/styled`, `@mui/material-nextjs`.
- No change to the agent service, the packet endpoint or its prompt, the risk model, the policy or the packet evals; the model hash and the frozen packet results stay valid. The `/api/packet` and `/api/analyze` routes are reused as they are.
- No model spend in tests (the scripted service). Bundle size grows with MUI and a roughly 250 KB cases file; both are measured in the tasks.
- Out of scope: real accounts or a shared database, a payer-side view or any simulated payer response, editing the preparing clinician's answers, dark mode, mobile layouts beyond a usable narrow width, changing the policy, the note reader or the evals.
- Eval categories affected: none graded by the harness; the web tests cover the new behavior and the safety/wording rules (no verdict words, no care gating).
