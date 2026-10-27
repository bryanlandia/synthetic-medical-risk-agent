import json
from pathlib import Path

import pytest

from risk_model import intake
from risk_model.labs import LAB_KEYS

DATA = json.loads((Path(__file__).parent / "wordings.json").read_text())["messages"]


def panel(text):
    return {e["lab"]: e["value"] for e in intake.view_from_text(text)["panel"]}


@pytest.mark.parametrize("entry", DATA, ids=lambda e: e["text"][:40].replace("\n", " "))
def test_each_wording_gives_exactly_the_labs_listed_and_leaves_the_rest_null(entry):
    got = panel(entry["text"])
    assert {k: v for k, v in got.items() if v is not None} == pytest.approx(entry["read"])
    assert {k for k, v in got.items() if v is None} == set(LAB_KEYS) - set(entry["read"])


def test_the_file_has_enough_variety_and_explains_every_wording_that_is_not_read():
    assert len(DATA) >= 20
    unread = [e for e in DATA if "unread" in e]
    assert len(unread) >= 5 and all(e["unread"].strip() and e["read"] == {} for e in unread)
    assert sum(1 for e in DATA if e["read"]) >= 12


def test_no_wording_is_read_as_a_value_it_does_not_state():
    """A wrong value is worse than a missing one: whatever is read must be a number written in the text."""
    import re

    for e in DATA:
        numbers = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", e["text"])]
        for lab, v in panel(e["text"]).items():
            if v is not None:
                assert any(abs(v - n) < 1e-9 or abs(v - n / f) / max(abs(v), 1) < 1e-6
                           for n in numbers for f in (1.0, 3.91, 0.0555, 0.0168, 0.01667)), (e["text"], lab, v)
