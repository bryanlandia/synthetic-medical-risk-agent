# training

Note reader and CPU risk classifier for a **FICTIONAL** disease (Velorin-Kessler syndrome). All data is synthetic;
nothing here is medical advice.

- `src/training/` fits and evaluates (scikit-learn, MLflow). Train data is the train split of `data_gen/data_llm/`
  **without the dev ids**; `test` and `adversarial` are refused by the loader.
- `src/risk_model/` is the inference package: numpy and the standard library only, so the agent can load the committed
  model files without scikit-learn or MLflow.

Run from `training/` with `UV_PYTHON_PREFERENCE=only-managed PATH=$HOME/.local/bin:$PATH uv run ...`:

| Command | What it does |
|---|---|
| `training train` | fit the reader and the classifier on train without dev, choose settings on dev, write `model/`, log an MLflow run |
| `training reader` | fit and score only the note reader (writes `model/reader.json`, `reader_report.json`) |
| `training lexicon` | regenerate `data/symptom_lexicon.json` |
| `training card` | rewrite `model/MODEL_CARD.md` from the manifest and result files |
| `training latency` | time one report at a time over 500 dev records; model size |
| `training freeze` | record the model hash (needs a dev run) so `test` and `adversarial` can be scored once each |
| `evals run --system classifier --split dev` | score the committed model through the harness |
| `evals compare` | classifier against the frontier baseline, paired, with intervals |

Layout: `src/risk_model/` is the inference package (numpy and the standard library only: reader, classifier, report
assembly, data-quality checks). `src/training/` fits and evaluates. `model/` holds the committed model files (`reader.json`,
`classifier.json`), the manifest with the model hash, the metrics and the model card. `config/grid.json` is the candidate
grid, declared before any dev scoring. `data/symptom_lexicon.json` is the symptom lexicon. `mlruns/` (MLflow) is not committed.

The classifier system is run from this folder because it depends on `evals`, not the other way round.
