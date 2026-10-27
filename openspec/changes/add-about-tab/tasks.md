## 1. Content

- [x] 1.1 Create `web/content/about.md` with the ten sections and suggested sentences from the design's outline (a `##` heading each, then a paragraph starting "*Suggested content:*"). Eval: a test reads the file and finds the ten headings; every sentence in it matches something the repository records (read once against `evals/README.md` and the model card).

## 2. The tab

- [x] 2.1 Extract the markdown renderer and its styles from the model-card tab into `web/components/Markdown.tsx`, with links opening in a new tab with `rel="noopener noreferrer"` and no images. Switch the model-card tab to it. Eval: the existing model-card tests pass unchanged.
- [x] 2.2 Add the "About this project" tab to `Demo.tsx`, reading `about.md` through `lib/content.ts`, with the banner as on every tab. Eval: Playwright opens the tab and finds every `##` heading in the file, in order.
- [x] 2.3 Test link safety and isolation: a link in the rendered text has `target="_blank"` and `rel` containing `noopener` and `noreferrer`, and opening the tab makes no request to another origin. Eval: the test fails if the `rel` attribute is removed.

## 3. Documentation and validation

- [x] 3.1 Add a short note to `web/README.md` on editing `about.md` (and how to find the sections still marked "Suggested content"). Eval: the README names the file and the marker.
- [x] 3.2 Run the web tests and typecheck, the model-card and demo-patient freshness tests in `training/` and `evals/`, and `openspec validate add-about-tab --strict`.
