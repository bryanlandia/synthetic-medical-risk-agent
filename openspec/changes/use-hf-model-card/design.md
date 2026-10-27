# Design

## Context

`training/src/training/model_card.py` builds `training/model/MODEL_CARD.md` from `manifest.json`, `metrics.json`, `reader_report.json`, `run.json` and the result summaries under `evals/results/classifier/`. A test (`test_model_card.py`) requires the committed card to be byte-identical to a fresh render and to name the model hash. The hash is over `reader.json` and `classifier.json` only, so rewriting the card cannot change it. The next change, `add-web-demo`, will show the card on a page; see proposal.md for why the format comes first.

## Goals / Non-Goals

**Goals:** the Hugging Face template's metadata block and section order; every number machine-checkable against a result file; nothing invented to fill a section.

**Non-Goals:** publishing to the Hub; a card for the agent's prompt and guards (the agent's results live in `evals/README.md`); any change to the model, the evals or the results.

## Decisions

**1. The card stays generated.** The generator is rewritten, not replaced by a hand-written file, so the existing guarantee (the card cannot drift from the files) holds. Alternative: a static template with placeholders filled by hand each run; rejected because drift is the failure the current test exists to prevent.

**2. Section map.** Existing content moves, none is dropped:

| Template section | Content |
|---|---|
| Model Details | developed by (the repository owner, with the repository URL), type (note reader plus logistic risk classifier), language (English, synthetic notes), license, finetuned from: none (trained from scratch), the model hash, seed, dataset config hash, MLflow run |
| Model Sources | repository; demo: none yet |
| Uses | Direct Use (the portfolio demo), Downstream Use (the agent service calls it as a tool), Out-of-Scope Use (any real patient, disease or decision) |
| Bias, Risks, and Limitations | today's "Known weaknesses", plus the dev-optimism and synthetic-rule caveats |
| How to Get Started | a runnable snippet using `risk_model` |
| Training Details | data and splits, the note reader and its leave-one-setting-out finding, hyperparameters, size and speed, reproduction |
| Evaluation | testing data, metrics, dev results, then test, adversarial and trials results |
| Model Examination | the reader's held-out and injection findings and where the lexicon and coefficients are |
| Environmental Impact | "not measured": it trains in seconds on a CPU; no figure is given |
| Technical Specifications | architecture, the two model files and their sizes, the inference-only package |
| Citation | none |
| Glossary | the fictional labs, units and typical values and the five symptoms, generated from `risk_model.labs` |
| More Information, Authors, Contact | the repository URL |

**3. Metadata is emitted by code without a YAML library.** JSON strings and numbers are valid YAML, so the generator writes the block with `json.dumps` for each scalar and fixed indentation. The runtime path gains no dependency. The test parses the block with a pinned `pyyaml` (test dependency only) and compares it with the result files. Alternative: emit with PyYAML; rejected to keep `training`'s runtime unchanged and the output byte-stable across PyYAML versions.

**4. The `model-index`.** One entry for the model, with a `tabular-classification` task and two result groups (dev and test) of four metrics each (`auc`, `brier`, `log_loss`, `ece`), values taken from the summary files at four decimals. The dataset entry names the synthetic dataset by its local name and config hash and says in the card that it is not a Hub dataset. Intervals and targets stay in the body tables. Tags: `synthetic-data`, `fictional-disease`, `not-for-clinical-use`, `tabular-classification`. No `library_name` is set because the model is not loadable by a Hub library.

**5. The example is tested by running it.** The "How to Get Started" snippet is a fenced Python block; a test extracts it and runs it against the committed model, so a rename in `risk_model` breaks the suite and not the reader's first try.

**6. The glossary comes from `risk_model.labs`.** The lab names, units and typical values are read from the table the inference code uses, so the card and the code cannot disagree.

## Risks / Trade-offs

- **License.** The repository has no license file. The card says `license: other` with the line "No license is granted; this is a portfolio demonstration" until the owner picks one; changing it is a one-line edit and a regeneration. Flagged for the owner, not decided here.
- **Template fit.** Some template sections (Citation, Environmental Impact) do not apply. The card keeps them with a one-line "not applicable" or "not measured" so a reader sees they were considered; the cost is a few near-empty headings.
- **The metadata duplicates the body.** The numbers appear in both; the test that compares them to the result files is what keeps them honest.
- **Hub validation.** The `model-index` is shaped for the Hub but is not validated against it here, since nothing is pushed. If the card is published later, a validation step belongs to that change.

## Open Questions

- The license (above). Default until answered: `other`, with the sentence above.
