## 1. About tab and assets

- [x] 1.1 Render a lone `![alt](web/public/name.svg)` line as a figure from this site in `web/components/AboutTab.tsx`, with its style in `web/app/globals.css`, and keep the renderer refusing images; verify the About tab's images all end in `.svg` on this site and the tab requests nothing from another origin (`tests/demo.spec.ts`).
- [x] 1.2 Draw `web/public/pathway.svg` and `web/public/request-packet.svg`, each with its own title, description and light background; verify both render without clipped text (screenshots) and load in the About tab.
- [x] 1.3 Add a test that both diagrams are shown, load from this site and have alt text of real length, and that no repository path or code block is left on the page; verify with `npx playwright test tests/demo.spec.ts -g About`.

## 2. Text

- [x] 2.1 Rewrite the About opening for the two scenarios and the packet paragraph as a list in `web/content/about.md`, drop "two ledgers" for "two costs", and update the story test's phrase; verify the story tests pass (no digits, percent or dollar signs in the story sections).
- [x] 2.2 Change the panel to "creates rework for the institution" in `web/lib/copy.ts`; verify the panel and help-dialog tests pass.

## 3. Verify and archive

- [x] 3.1 Run the full `npm test` in `web/` and `npm run typecheck`; verify all specs pass.
- [x] 3.2 Validate the delta (`openspec validate about-text-and-diagrams`) and, after merge, archive the change; verify the main `web-demo` spec holds the new requirements.
