from pathlib import Path

import pytest
from evals.graders import true_warning_types
from evals.records import input_view

import risk_model
from risk_model import quality
from risk_model.reader import Reading
from training import data

MODEL = None


def view(note="", **panel):
    entries = []
    for lab, unit, value in (("velorin_index", "mg/dL", 100.0), ("serum_k17", "mmol/L", 4.2), ("tarnic_acid", "umol/L", 300.0)):
        entries.append({"lab": lab, "unit": unit, "value": panel.get(lab, value)})
    return {"patient_id": "P1", "panel": entries, "note": note}


def types(v, reading=None):
    return {(w["type"], w["lab"]) for w in quality.check(v, reading or Reading({}))}


def test_missing_value_one_per_lab():
    assert types(view(velorin_index=None, tarnic_acid=None)) == {("missing_value", "velorin_index"), ("missing_value", "tarnic_acid")}


@pytest.mark.parametrize("bad", [-100.0, 1000.0])
def test_impossible_value(bad):
    assert types(view(velorin_index=bad)) == {("impossible_value", "velorin_index")}


def test_unit_mismatch_when_the_note_states_the_alternate_unit():
    assert types(view("Serum K-17 (K17): 16.4 mg/dL")) == {("unit_mismatch", "serum_k17")}  # 4.2 x 3.91 = 16.42


def test_contradiction_when_the_note_value_disagrees_with_the_panel():
    assert types(view("Velorin index 140 mg/dL")) == {("contradiction", "velorin_index")}


def test_an_alternate_unit_value_that_also_disagrees_is_both():
    assert types(view("Serum K-17 (K17): 25 mg/dL")) == {("unit_mismatch", "serum_k17"), ("contradiction", "serum_k17")}


def test_a_stated_value_that_agrees_is_not_a_warning():
    assert types(view("Velorin index 100 mg/dL, Serum K-17 4.2 mmol/L")) == set()


def test_no_contradiction_is_raised_against_a_missing_or_impossible_panel_value():
    assert types(view("Velorin index 104 mg/dL", velorin_index=None)) == {("missing_value", "velorin_index")}
    assert types(view("Velorin index 104 mg/dL", velorin_index=1040.0)) == {("impossible_value", "velorin_index")}


def test_a_symptom_conflict_is_a_warning_without_a_lab():
    assert types(view(), Reading({}, conflicts=["tremor"])) == {("note_flag_disagreement", None)}


def test_warnings_come_in_a_fixed_order():
    v = view("Serum K-17 25 mg/dL", velorin_index=None, tarnic_acid=1500.0)
    assert [w["type"] for w in quality.check(v, Reading({}))] == ["missing_value", "impossible_value", "unit_mismatch", "contradiction"]


def test_a_view_with_ground_truth_is_rejected():
    with pytest.raises(ValueError, match="label"):
        quality.check({**view(), "label": 1}, Reading({}))


def test_data_quality_on_the_train_records_matches_the_labels(dataset):
    model = risk_model.load(Path(__file__).resolve().parents[1] / "model")
    recs = data.training_records(dataset)[:800]
    stats = {t: [0, 0, 0] for t in ("missing_value", "unit_mismatch", "contradiction")}
    for r in recs:
        said = {w["type"] for w in model.report(input_view(r))["data_quality"]}
        truth = true_warning_types(r)
        for t in stats:
            stats[t][0] += t in truth
            stats[t][1] += t in said
            stats[t][2] += t in truth and t in said
    for t, (has, warned, both) in stats.items():
        assert has > 20, t
        assert both / has >= 0.95, (t, "recall", both, has)
        assert both / warned >= 0.97, (t, "precision", both, warned)
