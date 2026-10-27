## 1. Generator

- [x] 1.1 Rewrite `model_card.render` to emit the metadata block (tags, `model-index` with dev and test AUC, Brier, log loss, ECE) written without a YAML library, then the template's sections in order, moving the existing content as the design's section map says and adding the sections that did not exist (sources, downstream and out-of-scope use, model examination, environmental impact, technical specifications, citation, more information, authors, contact). Eval: the regenerated card contains every heading in order and the model hash, the notice and the out-of-scope use.
- [x] 1.2 Generate the glossary from `risk_model.labs` (name, abbreviation, unit, typical value) and the five symptoms, and write the "How to Get Started" snippet. Eval: a test fails if a lab in `risk_model.labs` is missing from the glossary.
- [x] 1.3 Add `pyyaml` (pinned) as a test dependency of `training/` and `uv sync`. Eval: `uv run pytest -q` in `training/` imports it.

## 2. Tests

- [x] 2.1 Update `training/tests/test_model_card.py`: the layout (metadata block first, headings in the template's order, notice present, out-of-scope use present), the metadata parses and every metric equals the dev and test summary files, the committed card equals a fresh render, and the stale-card test still holds. Replace the old needles ("Intended use", "Known weaknesses") with the new headings and keep the content needles (Leave-one-setting-out, Negative for, excluding the 500 dev records, never served).
- [x] 2.2 Add a test that extracts the "How to Get Started" snippet and runs it against the committed model, returning a report with a probability in [0, 1]. Eval: renaming `risk_model.load` makes it fail.

## 3. Regenerate and document

- [x] 3.1 Run `uv run training card` and commit the new `MODEL_CARD.md`. Eval: `pipeline.model_hash` is still `414c2d467c87…`, `classifier.json` and `reader.json` are unchanged (`git diff` shows only the card), and `uv run evals regression` still passes.
- [x] 3.2 Update `training/README.md` and the classifier line in `AGENTS.md` if they describe the card's layout. Read the rendered card once for sections that read as filler or claim something the files do not show.
- [x] 3.3 Run the `training/` suite and `openspec validate use-hf-model-card --strict`.
