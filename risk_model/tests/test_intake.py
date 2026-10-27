import pytest

import risk_model
from risk_model import intake
from risk_model.labs import LAB_KEYS, LAB_BY_KEY


def panel(view):
    return {e["lab"]: e["value"] for e in view["panel"]}


def warnings(report):
    return {(w["type"], w["lab"]) for w in report["data_quality"]}


def test_some_labs_give_eight_entries_two_with_values_and_the_note_is_the_message():
    text = "Velorin index 108 mg/dL, Tarnic acid 310 umol/L. Denies shaking."
    view = intake.view_from_text(text)
    assert [e["lab"] for e in view["panel"]] == list(LAB_KEYS) and view["note"] == text
    assert {k: v for k, v in panel(view).items() if v is not None} == {"velorin_index": 108.0, "tarnic_acid": 310.0}
    assert set(view) == {"patient_id", "panel", "note"}
    assert all(set(e) == {"lab", "value", "unit"} and e["unit"] == LAB_BY_KEY[e["lab"]].unit for e in view["panel"])


def test_no_labs_gives_all_null():
    view = intake.view_from_text("The patient reports fatigue and dizziness.")
    assert set(panel(view).values()) == {None}


def test_the_same_text_always_gives_the_same_view():
    text = "VLI 99 mg/dL; K17 3.9 mmol/L; TAC 301 umol/L. No tremor."
    assert intake.view_from_text(text) == intake.view_from_text(text)


def test_a_lab_named_without_a_number_is_null():
    view = intake.view_from_text("The Velorin index was within normal limits; Serum K-17 (K17) not drawn.")
    assert set(panel(view).values()) == {None}


def test_a_value_in_the_alternate_unit_is_converted_to_the_usual_unit():
    view = intake.view_from_text("Serum K-17 15.4 mg/dL")
    assert panel(view)["serum_k17"] == pytest.approx(15.4 / 3.91)


def test_the_first_stated_value_wins():
    view = intake.view_from_text("Velorin index 104 mg/dL ... later Velorin index 140 mg/dL")
    assert panel(view)["velorin_index"] == 104.0


def test_an_impossible_value_is_passed_on_as_written():
    assert panel(intake.view_from_text("Velorin index 1040 mg/dL"))["velorin_index"] == 1040.0


# --- the warnings the existing checks give on an intake view (task 2.2) -----------------------------------------------------

@pytest.fixture(scope="module")
def model():
    import os
    from pathlib import Path

    directory = Path(os.environ.get("RISK_MODEL_DIR") or Path(__file__).resolve().parents[2] / "training" / "model")
    return risk_model.load(directory)


def report_for(model, text):
    return model.report(intake.view_from_text(text))


def test_alternate_unit_gives_unit_mismatch(model):
    assert ("unit_mismatch", "serum_k17") in warnings(report_for(model, "Serum K-17 15.4 mg/dL. Denies shaking."))


def test_a_later_disagreeing_value_gives_contradiction(model):
    rep = report_for(model, "Velorin index 104 mg/dL. Recheck: Velorin index 140 mg/dL.")
    assert ("contradiction", "velorin_index") in warnings(rep)
    assert rep["labs_used"][0] == {"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}


def test_a_lab_not_stated_gives_missing_value(model):
    w = warnings(report_for(model, "Velorin index 108 mg/dL."))
    assert {("missing_value", k) for k in LAB_KEYS if k != "velorin_index"} <= w
    assert ("missing_value", "velorin_index") not in w


def test_an_impossible_value_is_flagged_and_scores_like_a_missing_lab(model):
    impossible = report_for(model, "Velorin index 1040 mg/dL. Tarnic acid 310 umol/L.")
    missing = report_for(model, "Tarnic acid 310 umol/L.")
    assert ("impossible_value", "velorin_index") in warnings(impossible)
    assert abs(impossible["probability"] - missing["probability"]) <= 0.01
    assert "velorin_index" not in {u["lab"] for u in impossible["labs_used"]}


def test_a_message_with_no_labs_still_scores_and_warns_for_every_lab(model):
    rep = report_for(model, "Reports fatigue and dizziness.")
    assert rep["status"] == "scored" and {w["lab"] for w in rep["data_quality"] if w["type"] == "missing_value"} == set(LAB_KEYS)


def test_a_thousands_comma_is_an_impossible_value_the_classifier_flags(model):
    rep = report_for(model, "Tarnic acid 1,040 umol/L. Velorin index 108 mg/dL.")
    assert ("impossible_value", "tarnic_acid") in warnings(rep)
    assert "tarnic_acid" not in {u["lab"] for u in rep["labs_used"]}


def test_a_decimal_comma_is_read_as_the_value_it_says(model):
    rep = report_for(model, "Dorrin ratio 0,98. Velorin index 108,3 mg/dL.")
    used = {u["lab"]: u["value"] for u in rep["labs_used"]}
    assert used == {"dorrin_ratio": 0.98, "velorin_index": 108.3}
