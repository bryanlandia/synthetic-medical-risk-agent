import json
from pathlib import Path

import risk_model
from risk_model import estimate_start
from risk_model.estimate import BANDS

FILE = Path(__file__).resolve().parents[2] / "web" / "content" / "estimate.json"


def test_the_committed_content_file_is_what_the_model_builds():
    assert json.loads(FILE.read_text()) == json.loads(json.dumps(estimate_start.build()))  # regenerate with uv run python -m risk_model.estimate_start


def test_the_opening_patient_is_borderline_and_invented():
    content = json.loads(FILE.read_text())
    assert 0.4 <= content["estimate"]["probability"] <= 0.6 and content["estimate"]["band"] == "uncertain"
    assert "invented" in content["notice"] and content["model_hash"] == risk_model.model_hash()
    assert content["estimate"]["band"] in BANDS


def test_every_lab_can_move_the_opening_patient_across_a_band_edge():
    model, start = risk_model.load(), estimate_start.START_LABS
    crossing = 0
    for lab in estimate_start.LABS:
        bands = {model.estimate({**start, lab.key: v}, estimate_start.START_SYMPTOMS)["band"] for v in (lab.plaus_lo, lab.plaus_hi)}
        crossing += bands != {"uncertain"}
    assert crossing >= 3  # a visitor who drags a few sliders to an end sees the band change
