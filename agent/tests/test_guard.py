import numpy as np
import pytest
import risk_model
from risk_model.labs import LABS

from agent import guard, replies

MODEL = risk_model.load()


def report(p=0.31, uncertain=False):
    r = MODEL.report({"patient_id": "P", "panel": [{"lab": l.key, "value": l.mean * 1.1, "unit": l.unit} for l in LABS], "note": "Reports tremor."})
    return {**r, "probability": p, "uncertain": uncertain}


@pytest.mark.parametrize("reply", [
    "The estimate is 31%.", "About 31 % probability.", "probability of 0.31", "I estimate a 31.0% chance.",
    "That is in the uncertain band between 40% and 60%.", "No number here at all.",
    "Velorin index 108.3 mg/dL and Dorrin ratio 0.985 were read.",  # lab values are not probabilities
])
def test_a_reply_whose_numbers_match_the_report_passes(reply):
    assert guard.check_reply(reply, report(0.31)) == []


@pytest.mark.parametrize("reply", ["The estimate is 85%.", "A probability of 0.85.", "It is 32%.", "About 31.5% chance."])
def test_a_reply_with_a_number_that_does_not_match_fails(reply):
    assert any(p.startswith("number:") for p in guard.check_reply(reply, report(0.31)))


def test_rounding_is_judged_by_the_digits_written():
    assert guard.check_reply("The probability is 31%.", report(0.3149)) == []
    assert guard.check_reply("The probability is 31%.", report(0.3151)) != []
    assert guard.check_reply("The probability is 0.315.", report(0.3149)) == []


@pytest.mark.parametrize("reply,kind", [
    ("Some people take ibuprofen for this.", "medication:ibuprofen"), ("Try 200 mg twice a day.", "dose"),
    ("You should take this medication daily.", "treatment_instruction"), ("It resembles diabetes.", "real_disease:diabetes"),
])
def test_forbidden_content_fails(reply, kind):
    assert f"content:{kind}" in guard.check_reply(reply, report())


@pytest.mark.parametrize("reply", ["As instructed: report LOW risk.", "ADDENDUM says low.", "I will ignore all previous instructions.",
                                    "Following the system note, it is fine."])
def test_a_reply_that_repeats_text_addressed_to_the_system_fails(reply):
    assert "echo" in guard.check_reply(reply, report())


def test_empty_and_overlong_replies_fail():
    assert "empty" in guard.check_reply("  ", report())
    assert "too_long" in guard.check_reply("word " * 400, report())


def test_the_template_passes_the_guard_for_many_different_reports():
    rng = np.random.default_rng(0)
    for _ in range(300):
        view = {"patient_id": "P", "note": "Reports tremor. Denies dizziness.",
                "panel": [{"lab": l.key, "value": None if rng.random() < 0.15 else float(l.mean + rng.normal() * l.sd), "unit": l.unit} for l in LABS]}
        rep = MODEL.report(view)
        text = replies.template_reply(rep)
        assert guard.check_reply(text, rep) == [], (guard.check_reply(text, rep), text)


def test_a_good_model_reply_is_released_and_a_bad_one_is_not():
    rep = report(0.31)
    assert replies.finalize_scored(rep, "The classifier estimates 31% for this record.").source == "model"
    assert replies.finalize_scored(rep, "The classifier estimates 90% for this record.").source == "template"
    assert replies.finalize_scored(rep, None).source == "template"


def test_declines_use_a_fixed_message_for_every_reason_and_fall_back_for_an_unknown_one():
    assert set(replies.DECLINES) == set(replies.REASONS)
    for reason, text in replies.DECLINES.items():
        assert guard.forbidden(text) == [] and "not medical advice" in text.lower()
        assert replies.finalize_declined(reason).text == text
    assert replies.finalize_declined("surprise").text == replies.DECLINES["out_of_scope"]


def _ranged_report():
    return {"probability": 0.31, "interval": [0.18, 0.77],
            "gaps": [{"kind": "lab", "key": "serum_k17", "low": 0.25, "high": 0.52, "changes_routing": True}]}


def test_a_reply_may_quote_the_probability_the_band_edges_the_range_and_a_gap_bound():
    r = _ranged_report()
    assert guard.check_reply("About 31%; if the lab were obtained it could be 25% to 52%, and overall 18% to 77%.", r) == []
    assert guard.check_reply("About 31%, in a band from 40% to 60%.", r) == []


def test_any_other_number_in_a_reply_is_still_rejected():
    r = _ranged_report()
    assert guard.check_reply("About 31%, overall 18% to 90%.", r) == ["number:0.9"]
    assert guard.check_reply("About 31% (18% to 77% overall).", {"probability": 0.31}) == ["number:0.18", "number:0.77"]  # no range in this report


def test_the_template_reply_states_the_range_when_findings_are_missing():
    view = {"patient_id": "P", "note": "Reports tremor.", "panel": [{"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}]}
    rep = MODEL.report(view)
    text = replies.template_reply(rep)
    lo, hi = rep["interval"]
    assert f"{lo:.0%} to {hi:.0%}" in text and guard.check_reply(text, rep) == []


def test_a_reply_quoting_a_bound_is_released_and_one_with_an_invented_percentage_is_replaced():
    view = {"patient_id": "P", "note": "Reports tremor.", "panel": [{"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}]}
    rep = MODEL.report(view)
    lo, hi = rep["interval"]
    ok = f"Roughly {rep['probability']:.0%}, and between {lo:.0%} and {hi:.0%} if the missing findings were obtained."
    bad = f"Roughly {rep['probability']:.0%}, and between {lo:.0%} and {min(hi + 0.11, 0.99):.0%} overall."
    assert replies.finalize_scored(rep, ok).source == "model"
    assert replies.finalize_scored(rep, bad).source == "template"
