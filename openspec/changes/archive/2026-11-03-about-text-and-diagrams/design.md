## Context

`web/content/about.md` is rendered by the About tab and is also the repository README (a symlink). The shared markdown renderer refuses images on purpose, so a description cannot load anything from another site. The tab already turns one comment line into a video player (`AboutTab.tsx`). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** diagrams that show on the site and on GitHub from one source line; no way for the text to load an image from elsewhere; diagrams readable without the page's colours.
**Non-Goals:** allowing images in the model card or in markdown generally; a drawing library; theming the SVGs to dark mode (the site is light-only, and each SVG carries its own background).

## Decisions

- **A markdown image line, matched by a strict pattern.** `![alt](web/public/<name>.svg)` on its own line. On GitHub the path is the file's real location in the repository; the About tab maps it to `/<name>.svg` on the site. Alternative: an HTML comment like the video line, which keeps the README clean but shows no diagram on GitHub, where most readers will see it.
- **The renderer keeps refusing images.** Only lines that match the pattern become figures, and only for `.svg` files in `web/public` with a plain file name. Anything else stays text and renders as nothing. Alternative: allow images in the renderer with a same-origin filter; rejected as a wider change for one use.
- **Alt text is the description.** The line's alt text is required by the pattern and carries the whole meaning of the diagram; each SVG also has its own title and description. A test checks that every figure has real alt text.
- **Plain SVG files, drawn by hand.** No build step, no dependency, and the files can be edited in any text editor. Each has its own light background so it reads on the site's panel and on GitHub in either theme.
- **Story sections stay free of figures.** File names and alt text in the "Where this fits" section contain no digits, percent or dollar signs, because the existing story test searches that section.

## Risks / Trade-offs

- [A diagram drifts from the system] → the packet diagram uses the same labels as the page's own "What produced this page?" key (code, model, person); a change to the pipeline should update both.
- [SVG text is small on a phone] → the figure scales to the page width; the alt text carries the content for anyone who cannot read it.
- [The README symlink shows the same text] → the About text avoids wording that only makes sense on the site.
