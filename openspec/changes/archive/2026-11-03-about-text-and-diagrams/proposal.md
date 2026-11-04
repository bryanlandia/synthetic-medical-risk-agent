## Why

The About text still describes the demo as a single-prompt chat UI, which stopped being true when the review queue and Estimate a risk arrived. Its "Where this fits" diagram is ASCII art in a code block, which reads poorly on the page and says nothing about the request packet. The phrase "two ledgers" reads as forced, and the panel's "rework for the clinic" blamed the wrong party.

## What Changes

- Rewrite the About text's opening to describe the two scenarios: the review queue (with the request packet) and Estimate a risk (with the assistant reached from it, and a collapsed free-text box). Rewrite the packet paragraph as a short list, with the labels that say what produced each part.
- Replace the ASCII pathway with an SVG graphic, and add a second SVG that shows how a request packet is made (chart, note reader, policy check, summary draft, sentence check, supervisor, with the preparer's answers and the context-only estimate).
- The About tab renders a line `![alt](web/public/name.svg)` as a figure whose image is served from this site. On GitHub the repository README (a link to the same file) shows the image through the repository path. The markdown renderer still refuses every other image.
- Say "two costs" instead of "two ledgers": the patient's time to diagnosis, and the institution's rework and appeals.
- The panel text says "creates rework for the institution".

Already applied in the working tree: `web/components/AboutTab.tsx`, `web/app/globals.css`, `web/content/about.md`, `web/lib/copy.ts`, `web/public/pathway.svg`, `web/public/request-packet.svg`, `web/tests/demo.spec.ts`. This change records the spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-demo`: the About story requirement (graphic pathway, the two costs by name), the links-are-safe requirement (images only from this site), and two new requirements: the diagrams, and the About text describing both scenarios.

`review-workspace` needs no delta: its panel requirement does not mention who bears the rework.

## Impact

- Code: `web/components/AboutTab.tsx` (figure lines), `web/app/globals.css` (figure style).
- Content: `web/content/about.md`, which is also the repository README.
- Assets: `web/public/pathway.svg`, `web/public/request-packet.svg`.
- Tests: `web/tests/demo.spec.ts` (images allowed only as same-site diagrams; a new test for the two diagrams; the story test says "two costs").
- No new dependencies; the About tab still makes no request to another site.
