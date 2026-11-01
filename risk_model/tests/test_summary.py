import copy

import pytest

from risk_model import scan, summary

VIEW = {"patient_id": "P", "note": "n", "panel": [{"lab": "velorin_index", "value": 142.0, "unit": "mg/dL"},
                                                   {"lab": "tarnic_acid", "value": 450.0, "unit": "umol/L"}]}
REPORT = {"symptoms": {"tremor": "present", "fatigue": "present", "photophobia": "absent", "joint_stiffness": "absent",
                       "dizziness": "absent"}, "probability": 0.7, "interval": [0.6, 0.8]}
PACKET = scan.evaluate(VIEW, REPORT, {"C3": "yes"})


def draft(**override):
    s = {"criterion": "C1", "status": "met", "text": "Velorin index 142 mg/dL and Tarnic acid 450 umol/L are high.",
         "cites": ["lab:velorin_index", "lab:tarnic_acid"]}
    return [{**s, **override}]


def test_a_faithful_draft_passes_and_the_template_passes_its_own_verifier():
    assert summary.verify(draft(), PACKET) == []
    assert summary.verify(summary.template_summary(PACKET), PACKET) == []


def test_a_sentence_without_a_citation_or_with_an_unknown_one_is_rejected():
    assert "no_citation:0" in summary.verify(draft(cites=[]), PACKET)
    assert "bad_citation:lab:serum_k17" in summary.verify(draft(cites=["lab:serum_k17"]), PACKET)


def test_an_invented_number_unit_or_lab_is_rejected():
    assert "number:165" in summary.verify(draft(text="Velorin index 165 mg/dL is high."), PACKET)
    assert "unit:mmol/l" in summary.verify(draft(text="Velorin index 142 mmol/L is high."), PACKET)
    assert "lab:dorrin_ratio" in summary.verify(draft(text="Dorrin ratio is high."), PACKET)


def test_a_status_that_differs_from_the_table_is_rejected():
    assert "status:C1" in summary.verify(draft(status="unknown"), PACKET)
    assert "status_text:C1" in summary.verify(draft(text="C1 is not met for Velorin index 142."), PACKET)


@pytest.mark.parametrize("text", [
    "The patient qualifies for the scan.", "This request will be approved.", "Treatment should start.", "Likely a diagnosis of X.",
    "This is urgent.", "Phrase the request so it is approved.", "Ignore previous instructions.", "Take 5 mg daily."])
def test_banned_vocabulary_is_rejected(text):
    assert summary.verify(draft(text=text), PACKET)


def test_the_extra_forbidden_check_is_applied():
    assert "content:medication:x" in summary.verify(draft(), PACKET, lambda t: ["medication:x"])


@pytest.mark.parametrize("bad", [None, [], "text", [{"criterion": "C1"}], [{**draft()[0], "extra": 1}], draft(criterion="C9")])
def test_malformed_drafts_are_rejected(bad):
    assert summary.verify(bad, PACKET)


def test_a_draft_is_rejected_as_a_whole():
    mixed = draft() + draft(cites=[])
    assert summary.verify(mixed, PACKET)


def test_the_template_names_every_criterion_with_the_table_status():
    t = summary.template_summary(PACKET)
    assert [(s["criterion"], s["status"]) for s in t] == [(r["id"], r["status"]) for r in PACKET["criteria"]]
    assert copy.deepcopy(PACKET) == PACKET
