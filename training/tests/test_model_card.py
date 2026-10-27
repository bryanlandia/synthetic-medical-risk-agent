import json
import shutil
from pathlib import Path

from training import model_card, pipeline

MODEL = Path(__file__).resolve().parents[1] / "model"


def test_the_committed_card_names_the_hash_of_the_committed_model_files():
    card = (MODEL / model_card.CARD_NAME).read_text()
    assert pipeline.model_hash(MODEL) in card
    assert json.loads((MODEL / "manifest.json").read_text())["model_hash"] == pipeline.model_hash(MODEL)


def test_the_committed_card_is_exactly_what_the_files_say():
    assert (MODEL / model_card.CARD_NAME).read_text() == model_card.render(MODEL)


def test_changing_a_model_file_makes_the_card_stale(tmp_path):
    shutil.copytree(MODEL, tmp_path / "m")
    m = tmp_path / "m"
    (m / "classifier.json").write_text(json.dumps({**json.loads((m / "classifier.json").read_text()), "intercept": 0.123}))
    assert pipeline.model_hash(m) not in (m / model_card.CARD_NAME).read_text()


def test_the_card_states_the_notice_the_intended_use_and_the_findings():
    card = (MODEL / model_card.CARD_NAME).read_text()
    for needle in ("ALL DATA IS SYNTHETIC", "not medical advice", "Intended use", "Leave-one-setting-out", "Known weaknesses",
                   "Negative for", "excluding the 500 dev records", "never served"):
        assert needle in card, needle
