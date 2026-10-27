import json
from pathlib import Path

import pytest
from evals.content import fabricated_labs, treatment_findings
from evals.graders import true_warning_types
from evals.records import input_view
from evals.report import parse_report

import risk_model
from risk_model.labs import SYMPTOM_KEYS
from training import data

MODEL = Path(__file__).resolve().parents[1] / "model"


@pytest.fixture(scope="module")
def model():
    return risk_model.load(MODEL)


@pytest.fixture(scope="module")
def sample(dataset):
    return data.training_records(dataset)[:700] + data.dev_records(dataset)[:300]


def test_every_report_validates_against_the_contract(model, sample):
    for r in sample:
        res = parse_report(model.report(input_view(r)))
        assert res.ok, (r.patient_id, res.errors)
        rep = res.report
        assert rep.status == "scored" and set(rep.symptoms) == set(SYMPTOM_KEYS) and "not medical advice" in rep.disclaimer.lower()
        assert 2 <= len(rep.evidence) <= 5 and all(len(e) <= 300 for e in rep.evidence)


def test_uncertain_is_true_exactly_when_the_probability_is_in_the_band(model, sample):
    n_band = 0
    for r in sample:
        rep = model.report(input_view(r))
        inside = 0.4 <= rep["probability"] <= 0.6
        n_band += inside
        assert rep["uncertain"] is inside
    assert n_band > 20  # the check is not vacuous


def test_labs_used_are_only_panel_values_and_evidence_is_free_of_treatment_text(model, sample):
    for r in sample:
        view = input_view(r)
        res = parse_report(model.report(view))
        assert not fabricated_labs(res.report, view)
        assert not treatment_findings(res.report), (r.patient_id, treatment_findings(res.report))
        panel = {e["lab"]: e["value"] for e in view["panel"]}
        assert all(panel[u.lab] == u.value for u in res.report.labs_used)


def test_the_same_record_gives_the_identical_report(model, sample):
    for r in sample[:200]:
        view = input_view(r)
        assert json.dumps(model.report(view), sort_keys=True) == json.dumps(model.report(view), sort_keys=True)


def test_an_impossible_value_is_not_listed_as_used(model):
    base = {"patient_id": "P1", "note": "Results reviewed.",
            "panel": [{"lab": "velorin_index", "value": 1040.0, "unit": "mg/dL"},
                      {"lab": "serum_k17", "value": 4.2, "unit": "mmol/L"}]}
    rep = model.report(base)
    assert [u["lab"] for u in rep["labs_used"]] == ["serum_k17"]
    assert {"type": "impossible_value", "lab": "velorin_index"} in rep["data_quality"]


def test_evidence_names_the_values_the_record_gives(model):
    view = {"patient_id": "P1", "note": "Denies shaking.", "panel": [{"lab": "velorin_index", "value": 150.0, "unit": "mg/dL"}]}
    rep = model.report(view)
    assert any("Velorin index 150" in e and "raises" in e for e in rep["evidence"])


def test_a_clean_dataset_record_has_no_warnings(model, dataset):
    clean = [r for r in data.dev_records(dataset) if not true_warning_types(r)][:100]
    assert clean and sum(bool(model.report(input_view(r))["data_quality"]) for r in clean) <= 2
