# risk_model

Inference for the note reader and the risk classifier of a **FICTIONAL** disease (Velorin-Kessler syndrome). All data is
synthetic; nothing here is medical advice.

numpy and the standard library only, so a service image does not carry scikit-learn or MLflow.

```python
import risk_model

model = risk_model.load()                   # RISK_MODEL_DIR, else training/model in this repository
report = model.report({"patient_id": "P1", "panel": [...], "note": "..."})
```

The model files (`reader.json`, `classifier.json`) are written by `training/` (`uv run training train`); this project only
reads them. `risk_model.load(directory)` takes an explicit directory; without one it uses the `RISK_MODEL_DIR` environment
variable, then `training/model` next to this project.

Tests here need no dataset and no other project: `uv run pytest -q` from this folder.
