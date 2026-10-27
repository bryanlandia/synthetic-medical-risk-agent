import json
from pathlib import Path

import risk_model

MODEL = Path(__file__).resolve().parents[2] / "training" / "model"


def test_the_hash_matches_the_manifest_the_training_run_wrote():
    assert risk_model.model_hash(MODEL) == json.loads((MODEL / "manifest.json").read_text())["model_hash"]


def test_load_takes_an_explicit_directory_then_the_environment_then_the_repository_default(monkeypatch, tmp_path):
    assert risk_model.default_directory() == MODEL
    monkeypatch.setenv("RISK_MODEL_DIR", str(tmp_path))
    assert risk_model.default_directory() == tmp_path
    view = {"patient_id": "P", "panel": [], "note": "Denies shaking."}
    assert risk_model.load(MODEL).report(view)["status"] == "scored"  # explicit directory wins over the environment
