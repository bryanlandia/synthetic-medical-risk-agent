# training

Note reader and CPU risk classifier for a **FICTIONAL** disease (Velorin-Kessler syndrome). All data is synthetic;
nothing here is medical advice.

- `src/training/` fits and evaluates (scikit-learn, MLflow). Train data is the train split of `data_gen/data_llm/`
  **without the dev ids**; `test` and `adversarial` are refused by the loader.
- `src/risk_model/` is the inference package: numpy and the standard library only, so the agent can load the committed
  model files without scikit-learn or MLflow.

Commands are added as each part lands. Run from `training/` with
`UV_PYTHON_PREFERENCE=only-managed PATH=$HOME/.local/bin:$PATH uv run ...`.
