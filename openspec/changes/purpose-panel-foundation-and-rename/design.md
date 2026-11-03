## Context

The panel text lives in one source (`web/lib/copy.ts`: `PURPOSE_TITLE`, `PURPOSE_PARAGRAPHS`) that the intro card, the help dialog and the tests all read, so the page and the checks cannot drift. The menu label is a literal in `Demo.tsx` and in tests. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** one source for the new wording; no verdict words; the foundation stays out of what is sent to the service.
**Non-Goals:** changing the About text or model card (they already name the foundation); renaming analytics event names; changing the free-text box or the model card view.

## Decisions

- **The foundation paragraph comes first, as its own paragraph.** It answers "why does this exist" before the scan and the packet. Alternative: append it at the end, which buries the motivation.
- **"Speed insurer coverage", not "approve".** The panel must not suggest the tool grants or refuses coverage, and the spec bans approved/denied/eligible/qualifies. The existing test for the closing sentence is kept.
- **Page copy only.** The foundation is not added to the packet request or the packet shown; `demo.spec.ts` already checks that, and this change does not touch it.
- **Rename by label only.** The analytics element name `menu:behind` stays, so the fixed set of names and past counts do not change.

## Risks / Trade-offs

- [The two unarchived changes modify the same requirements] → archive `case-view-clarity` and `estimate-a-risk` first; these deltas build on their text.
- [Longer panel] → one short paragraph; it stays dismissible and Reset restores it.
- [A test asserting the old title or label is missed] → search the repo for both old strings and run `npm test`.
