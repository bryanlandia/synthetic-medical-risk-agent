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
