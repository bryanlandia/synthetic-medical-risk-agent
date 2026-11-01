import json
import re
from pathlib import Path

from risk_model import policy

MODEL = Path(__file__).resolve().parents[2] / "training" / "model"


def _text() -> str:
    return (policy.POLICY_DIR / "pet_ct_k17.md").read_text() + (policy.POLICY_DIR / "pet_ct_k17.json").read_text()


def test_the_policy_defines_six_criteria_and_says_it_is_fictional():
    p = policy.load()
    assert [c["id"] for c in p["criteria"]] == list(policy.CRITERIA_IDS)
    assert "fictional" in p["notice"].lower() and "not medical advice" in p["notice"].lower()
    assert "fictional" in (policy.POLICY_DIR / "pet_ct_k17.md").read_text().lower()


def test_the_markdown_and_the_json_use_the_same_wording():
    md = (policy.POLICY_DIR / "pet_ct_k17.md").read_text()
    for text in policy.wording().values():
        assert text in md


def test_the_policy_quotes_no_coefficient_or_intercept():
    text = _text()
    assert not re.search(r"coef|intercept|weight|logit", text, re.I)
    clf = json.loads((MODEL / "classifier.json").read_text())
    numbers = [*clf["coef"], clf.get("intercept")]
    for n in filter(lambda v: isinstance(v, float), numbers):
        assert f"{abs(n):.3f}" not in text


def test_the_policy_is_version_two_and_states_that_its_thresholds_say_nothing_about_a_patient():
    p = policy.load()
    assert p["id"] == "fictional-k17-pet-ct-v2"
    assert "says nothing about any patient" in p["threshold_note"]
    assert p["threshold_note"] in (policy.POLICY_DIR / "pet_ct_k17.md").read_text()


def test_the_c1_thresholds_are_the_lab_mean_plus_one_sd_and_appear_in_the_wording():
    from risk_model.labs import LAB_BY_KEY

    thresholds = policy.load()["c1_thresholds"]
    assert list(thresholds) == ["velorin_index", "tarnic_acid", "dorrin_ratio"]
    for key, value in thresholds.items():
        lab = LAB_BY_KEY[key]
        assert value == lab.mean + lab.sd
        unit = "" if lab.unit == "ratio" else f" {lab.unit}"
        assert f"{lab.name} above {value:g}{unit}" in policy.wording()["C1"]
