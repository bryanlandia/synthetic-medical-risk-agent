# Proposal

## Why

The classifier's model card is a good document in a layout of our own. Anyone who has read a model card on the Hugging Face Hub expects a fixed order (metadata, model details, uses, bias and limitations, how to get started, training, evaluation) and a metadata block that tools can read. Using that layout makes the card familiar to a reviewer and lets the next change, the web demo, show it in a page and check it mechanically against the running service. It should be done before the web change so the page is built once against the final format.

## What Changes

- Rewrite the generated card (`training/model/MODEL_CARD.md`) into the Hugging Face model card template: a YAML metadata block (tags, metrics, a `model-index` with the dev and test results) followed by the template's sections in its order. The card stays generated from the manifest and the result files, so it cannot drift from the model.
- Fill the template honestly for this model: "finetuned from" is none (trained from scratch), "Out-of-Scope Use" is any real medical use, a section that does not apply says so in one line, and nothing is invented (training time and energy are "not measured").
- Add a "How to Get Started" snippet and a test that runs it against the committed model, and a glossary of the fictional labs generated from the same table the code uses.
- Keep the model hash, the synthetic-data notice and the existing findings (held-out settings, known weaknesses, final results, reproduction). Content moves; none is dropped.
- No change to the model, its hash, the evals or any result file. No spend.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `risk-classifier`: the model-card requirement now names the layout (the Hugging Face template's sections, in order, behind a machine-readable metadata block) and requires the metadata's numbers to equal the result files and the card to name the current model hash; two requirements are added for the metadata and the runnable snippet.

## Impact

- Code: `training/src/training/model_card.py` (the generator), `training/tests/test_model_card.py`, `training/README.md`.
- Files: `training/model/MODEL_CARD.md` is regenerated; no other committed file changes.
- Dependencies: one test-only dependency, a pinned YAML parser, to check the metadata block. The generator itself needs none.
- Later: `add-web-demo` renders this card on a page and compares its model hash with the running service's.
