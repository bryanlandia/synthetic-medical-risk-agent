## Why

The queue's introduction explains the scan and the packet but not why the tools exist. A visitor should learn that Velorin-Kessler syndrome (fictional) is treatable if caught early and becomes debilitating and expensive if not, and that the (fictional) Kessler Family Foundation sponsors these tools to speed insurer coverage of the confirming scan and to aid diagnosis. The panel title also names only the packet, though the panel explains the whole review. The menu label "Behind the demo" says little about what is inside (the model card and About), so it becomes "How it works".

## What Changes

- Retitle the queue's intro panel and the help control from "What is this packet for?" to "What are the review and packet for?".
- Add a first paragraph to the panel and the help dialog: the disease is a neurological disorder, treatable if caught early, debilitating and expensive otherwise; the foundation (marked fictional) sponsors these tools to speed insurer coverage of the confirming scan and to aid diagnosis. The wording avoids approved, denied, eligible and qualifies, and the closing statement that the tool decides nothing about care or coverage stays.
- Rename the navigation menu "Behind the demo" to "How it works" (button, view heading prefix, tests and documentation). Its contents (model card, About) do not change.
- The analytics event name for the menu is unchanged, so existing counts stay comparable.

Already applied in the working tree: `web/lib/copy.ts`, `web/components/Demo.tsx`, the Playwright specs and `web/README.md`. This change records the spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-workspace`: the panel's title and content; the "Demo notes" scenario that names the menu's views.
- `web-demo`: the menu name in the navigation, free-text, model-card, About and every-screen requirements.
- `usage-analytics`: the menu name in the list of counted clicks.

## Impact

- Code: `web/lib/copy.ts` (title, paragraphs), `web/components/Demo.tsx` (menu label, heading).
- Tests: `web/tests/{shell,review,demo,estimate,analytics}.spec.ts`.
- Docs: `web/README.md`.
- Ordering: `case-view-clarity` and `estimate-a-risk`, which modify the same requirements, were archived first; the deltas here are written on top of their text. The old "two scenarios under one title" requirement is removed and re-added under a new name because a MODIFIED block cannot rename a scenario.
