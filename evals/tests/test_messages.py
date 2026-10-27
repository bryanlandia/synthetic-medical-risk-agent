import pytest

from evals.messages import render_message
from evals.records import input_view


def test_a_message_lists_every_non_null_panel_value_then_the_note(dataset):
    rec = next(r for r in dataset.by_split["dev" if "dev" in dataset.by_split else "train"] if any(
        e.value is None for e in r.input.panel))
    view = input_view(rec)
    text = render_message(view)
    assert text.startswith("Labs:\n- ") and text.endswith("Note:\n" + view["note"])
    for e in view["panel"]:
        written = f"{e['value']:g} {e['unit']}" if e["value"] is not None else None
        assert (written in text) if written else True
    assert sum(line.startswith("- ") for line in text.split("Note:")[0].splitlines()) == sum(
        e["value"] is not None for e in view["panel"])


def test_a_message_has_no_ground_truth_field(dataset):
    for rec in dataset.by_split["train"][:200]:
        text = render_message(input_view(rec))
        truth = rec.ground_truth
        assert f"{truth.true_probability}" not in text and "true_probability" not in text and "label" not in text.lower().split("note:")[0]


def test_a_view_with_ground_truth_cannot_be_rendered():
    with pytest.raises(ValueError):
        render_message({"patient_id": "P", "panel": [], "note": "n", "label": 1})
