# risk_model

Inference for the note reader and the risk classifier of a **FICTIONAL** disease (Velorin-Kessler syndrome). All data is
synthetic; nothing here is medical advice.

numpy and the standard library only, so a service image does not carry scikit-learn or MLflow.

```python
import risk_model

model = risk_model.load()                   # RISK_MODEL_DIR, else training/model in this repository
report = model.report({"patient_id": "P1", "panel": [...], "note": "..."})
```

A scored report also carries `interval` and `gaps`: the lowest and highest probability if the labs and symptoms the record lacks were
obtained (a lab within two standard deviations of its mean, a symptom absent, possible or present), computed exactly from the logistic
model (`sensitivity.py`), and each missing item's own range. It is a range over missing findings, not a confidence interval: it does not
include uncertainty in how the model was fitted or calibrated. `LOGIC_VERSION` is 2 because of these fields; the model files are unchanged.


`model.estimate(labs, symptoms)` is the what-if estimate behind the web page's Estimate a risk scenario (`estimate.py`): eight labs (a value in the usual unit, or `None` for "not done") and five symptoms (`absent`, `possible` or `present`) give the probability, its band, a signed breakdown per input that adds up with the starting point to the score, and the message those inputs make as a note. No note is read and nothing is varied beyond the inputs. A lab value is rounded to the resolution the message writes it with. The message template is built so that the text intake and the note reader give back exactly the inputs; a test checks all 243 symptom combinations against 200 seeded lab settings. `uv run python -m risk_model.estimate_start ../web/content/estimate.json` rewrites the page's opening content (the lab limits and one invented borderline patient); a test fails when the committed file differs.

The model files (`reader.json`, `classifier.json`) are written by `training/` (`uv run training train`); this project only
reads them. `risk_model.load(directory)` takes an explicit directory; without one it uses the `RISK_MODEL_DIR` environment
variable, then `training/model` next to this project.

Tests here need no dataset and no other project: `uv run pytest -q` from this folder.
