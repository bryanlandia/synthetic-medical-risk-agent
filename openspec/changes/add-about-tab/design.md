# Design

## Context

The web page (`web/`) is a client component with three tabs (`Demo.tsx`): the chart, free text, and the model card. The model-card tab renders markdown with `react-markdown` and `remark-gfm` inside its own component, with styles under `.card-doc`. Content files live in `web/content/` and are read on the server by `lib/content.ts`, then passed to the client component as props. The page is statically rendered, and a Playwright test (run against the production build) already searches everything sent to the browser for the shared secret and the agent's address. See proposal.md for why the tab is wanted.

## Goals / Non-Goals

**Goals:** a place the owner can write the project description by editing one markdown file; a suggested outline in the file now; the same look and the same safety rules as the model-card tab.

**Non-Goals:** the final text (the owner writes it); a CMS, images or diagrams; a separate route or page (it is a tab); any figure that is not already recorded in the repository.

## Decisions

**1. The text is a committed markdown file, `web/content/about.md`.** The owner edits it like any README; no code changes are needed to rewrite it. It is read on the server by `lib/content.ts` (as the model card is) and rendered on the client. Alternative: text written into the React component; rejected because every edit would be a code change in JSX.

**2. One shared `Markdown` component.** The renderer, its plugins and its styles move from the model-card tab into `components/Markdown.tsx`; both tabs use it. Links get `target="_blank"` and `rel="noopener noreferrer"`, and images are not rendered (the About text may not load anything from another site). Alternative: copy the renderer into the new tab; rejected because the two would drift.

**3. The outline lives in the file as headings with a draft sentence or two.** Each section is a `##` heading followed by a paragraph that starts "*Suggested content:*" and says what to cover. The marker makes unwritten sections easy to find (search the file for it) and easy to delete as each is written. The sentences are suggestions for the owner and assert only what the repository already records. The outline:

| # | Heading | Suggested content |
|---|---|---|
| 1 | What this is | A portfolio demonstration of a decision-support panel for a fictional disease, Velorin-Kessler syndrome. Say who it is for, what a visitor can do on each tab, and that the evaluations, not the chart, are the main work. |
| 2 | Why a fictional disease | Real patient data was never an option. A made-up syndrome with a hidden scoring rule the project owns means the true answer is known, so every claim about accuracy can be checked, and nobody can mistake the output for medical advice. |
| 3 | How it fits together | A visitor's chart becomes one message; a small note reader and risk classifier score it on a CPU; an agent built on Claude Haiku 5.5 decides whether to score or decline and writes a short reply; code, not the model, supplies the numbers and the disclaimer. A small diagram would help. |
| 4 | The data | A seeded generator makes labs and notes; the notes are written by a language model in four documentation styles (AI scribe, EHR template, shorthand, copy-forward) and were checked by a rating gate before use. Mention the dev, test and adversarial splits and why the last two are looked at once each. |
| 5 | The classifier | A logistic risk model with a note reader, about 200 kB, answering in under a millisecond on a CPU. Say how it compares with simply prompting a frontier model (the repository has a paired comparison) and link to the Model card tab. |
| 6 | The agent and its guards | The scoring tool takes no arguments, so the model cannot change what is scored; declines use a closed set of reasons; a check replaces any reply that quotes a wrong number or names a drug; limits and a daily dollar cap bound the spend. Point at the injected-instruction example on the Try the agent tab. |
| 7 | How it is measured | Code-graded evals built with Inspect AI, targets set before the runs, 95% intervals with a plain-language verdict, protected splits looked at once, failing transcripts read by a person. Give the headline results and say which targets were missed. |
| 8 | What went wrong and what I learned | Honest notes: early prompts did poorly; label noise caps any system's score; a small share of requests make a second, refused tool call; the guards had to be built on a platform that keeps no state between requests. |
| 9 | What would change with real data | This is not a medical device and was never validated on real patients. A real deployment would live inside an existing record system, use verified context, and need clinical validation and regulatory review. |
| 10 | Stack, code and contact | Next.js and a Python function on Vercel, FastAPI and Strands, Inspect AI, MLflow, an Upstash store for the limits, specs kept with OpenSpec. Link the repository and give a way to reach the author. |

**4. Tests do not freeze the text.** They check that the tab exists and is reachable from the others, that every `##` heading in the file is shown as a heading in the file's order (read from the file, so rewording passes), that links carry `rel` and `target`, that the banner is present, and that the page makes no request to another origin when the tab is opened. The existing leak test keeps covering the secret and the agent's address.

## Risks / Trade-offs

- **Draft sentences on a public page.** Until the owner rewrites them, visitors see the "Suggested content" lines. They are written to be accurate and harmless, and the marker makes the draft status plain. The owner can hold the tab back by not deploying, or delete the marker lines they have replaced.
- **Numbers go stale.** The outline avoids figures on purpose. When the owner adds any, they should come from `evals/README.md` and the result files, which are the recorded source.
- **The shared renderer changes the model-card tab.** The extraction is covered by the existing model-card tests, which must still pass unchanged.

## Open Questions

None.
