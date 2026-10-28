# Proposal

## Why

The demo page lets a visitor try the agent, but nothing on it says what the project is, why the disease is fictional, how the pieces fit, or how the work was measured, and the measuring is the part that matters most. A visitor, especially a reviewer, should be able to learn that in a few minutes without opening the repository. The owner wants to write that description in their own words; this change gives them the place and a suggested outline so the writing is the only work left.

## What Changes

- Add a fourth tab, **About this project**, to the web page. It shows a markdown file from `web/content/` and is reachable from every other tab, with the synthetic-data banner as on every screen.
- Add `web/content/about.md` with a **suggested outline**: ten sections, each with a sentence or two saying what to cover. The sentences are drafts for the owner to replace; they make no claim beyond what the repository already records.
- Reuse the model-card tab's markdown renderer so both tabs look alike (one shared component and one set of styles), and make links in the About text open safely.
- Add tests that the tab exists and renders every heading in the file, that links are safe, and that the banner is present.
- No change to the agent, the model, the evals or any recorded result.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `web-demo`: a tab that describes the project from a committed markdown file, rendered with the shared renderer, with safe links and the page's banner.

## Impact

- Code: `web/components/Demo.tsx` (the tab), a shared `web/components/Markdown.tsx` (extracted from the model-card tab), `web/lib/content.ts` (reads the file), `web/app/globals.css`.
- Content: new `web/content/about.md`, the file the owner edits.
- Tests: `web/tests/` (Playwright, against the scripted service as before).
- Ordering: this change adds to the `web-demo` spec created by `add-web-demo`, which is merged but not yet archived. Archive `add-web-demo` first.
