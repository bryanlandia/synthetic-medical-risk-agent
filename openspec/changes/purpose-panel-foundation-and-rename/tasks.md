## 1. Panel wording

- [x] 1.1 Retitle the panel and help control "What are the review and packet for?" and add the foundation paragraph in `web/lib/copy.ts`; verify the panel and the help dialog show the same text and no verdict word appears (`tests/review.spec.ts`).
- [x] 1.2 Extend the panel test in `web/tests/review.spec.ts` to check for the sponsor (Kessler Family Foundation, marked fictional), "treatable if caught early" and "decides nothing about the patient's care or about coverage"; verify with `npm test`.

## 2. Menu rename

- [x] 2.1 Rename "Behind the demo" to "How it works" in `web/components/Demo.tsx`, the Playwright specs and `web/README.md`; verify with a search that no "Behind the demo" remains under `web/`, and `npm run typecheck` passes.
- [x] 2.2 Run the full `npm test` in `web/`; verify every spec passes, including the heading "How it works: Model card" and the navigation order Review queue, Estimate a risk, How it works.

## 3. Specs

- [x] 3.1 Validate the deltas (`openspec validate purpose-panel-foundation-and-rename`) and confirm `case-view-clarity` and `estimate-a-risk` are archived first; verify no "Behind the demo" or "What is this packet for?" remains in `openspec/specs/` after this change is synced.
