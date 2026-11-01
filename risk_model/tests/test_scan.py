import pytest

from risk_model import scan

UNITS = {"velorin_index": "mg/dL", "tarnic_acid": "umol/L", "dorrin_ratio": "ratio"}
HIGH = dict(velorin_index=150.0, tarnic_acid=450.0)


def view(**labs):
    return {"patient_id": "P", "note": "n", "panel": [{"lab": k, "value": v, "unit": UNITS[k]} for k, v in labs.items()]}


def report(**symptoms):
    base = {s: "not_mentioned" for s in ("tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness")}
    return {"symptoms": {**base, **symptoms}, "probability": 0.7, "interval": [0.6, 0.8]}


def row(packet, cid):
    return next(r for r in packet["criteria"] if r["id"] == cid)


def test_two_high_labs_meet_c1_and_cite_them():
    p = scan.evaluate(view(**HIGH), report())
    assert row(p, "C1")["status"] == "met"
    assert row(p, "C1")["cites"] == ["lab:velorin_index", "lab:tarnic_acid"]


def test_one_high_one_within_one_unreported_is_unknown_with_a_gap():
    p = scan.evaluate(view(velorin_index=150.0, tarnic_acid=300.0), report())
    assert row(p, "C1")["status"] == "unknown"
    assert next(g for g in p["gaps"] if g["criterion"] == "C1")["items"] == ["dorrin_ratio"]


def test_c1_cannot_be_met_when_two_are_within_range():
    assert row(scan.evaluate(view(velorin_index=100.0, tarnic_acid=300.0), report()), "C1")["status"] == "unmet"


def test_alternate_unit_is_converted_but_cited_as_written():
    v = {"patient_id": "P", "note": "n", "panel": [{"lab": "velorin_index", "value": 8.325, "unit": "mmol/L"},
                                                   {"lab": "tarnic_acid", "value": 450.0, "unit": "umol/L"}]}
    p = scan.evaluate(v, report())
    assert row(p, "C1")["status"] == "met"
    ev = next(e for e in p["evidence"] if e["id"] == "lab:velorin_index")
    assert ev["value"] == 8.325 and ev["unit"] == "mmol/L" and "8.325 mmol/L" in ev["text"]


def test_an_impossible_value_does_not_count_and_is_a_gap():
    p = scan.evaluate(view(velorin_index=150.0, tarnic_acid=300.0, dorrin_ratio=9.0), report())
    assert row(p, "C1")["status"] == "unknown"  # the impossible value is unreported, so C1 could still be met
    assert next(g for g in p["gaps"] if g["criterion"] == "C1")["items"] == ["dorrin_ratio"]
    p = scan.evaluate(view(velorin_index=150.0, dorrin_ratio=9.0), report())
    assert row(p, "C1")["status"] == "unknown"
    assert "lab:dorrin_ratio" not in {e["id"] for e in p["evidence"]}
    assert set(next(g for g in p["gaps"] if g["criterion"] == "C1")["items"]) == {"tarnic_acid", "dorrin_ratio"}


def test_c2_tremor_and_another_symptom_present_is_met():
    p = scan.evaluate(view(), report(tremor="present", fatigue="present"))
    assert row(p, "C2")["status"] == "met"
    assert row(p, "C2")["cites"] == ["symptom:tremor", "symptom:fatigue"]


def test_c2_hedged_tremor_is_unknown_and_named_in_the_gap():
    p = scan.evaluate(view(), report(tremor="possible", fatigue="present"))
    assert row(p, "C2")["status"] == "unknown"
    assert "tremor" in next(g for g in p["gaps"] if g["criterion"] == "C2")["items"]


def test_c2_absent_tremor_is_unmet_and_possible_never_counts_as_present():
    assert row(scan.evaluate(view(), report(tremor="absent", fatigue="present")), "C2")["status"] == "unmet"
    assert row(scan.evaluate(view(), report(tremor="present", fatigue="possible")), "C2")["status"] == "unknown"
    absent = dict(fatigue="absent", photophobia="absent", joint_stiffness="absent", dizziness="absent")
    assert row(scan.evaluate(view(), report(tremor="present", **absent)), "C2")["status"] == "unmet"


def test_attestations_decide_c3_to_c6_only_and_nothing_answered_is_unknown():
    p = scan.evaluate(view(), report(), None)
    assert [row(p, c)["status"] for c in ("C3", "C4", "C5", "C6")] == ["unknown"] * 4
    assert {g["criterion"] for g in p["gaps"]} >= {"C3", "C4", "C5", "C6"}
    p = scan.evaluate(view(), report(), {"C3": "yes", "C5": "no"})
    assert row(p, "C3")["status"] == "met" and row(p, "C5")["status"] == "unmet" and row(p, "C4")["status"] == "unknown"
    assert row(p, "C3")["cites"] == ["attest:C3"]


def test_a_note_that_claims_history_does_not_answer_anything():
    v = view()
    v["note"] = "Symptoms for 8 weeks, no prior imaging."
    p = scan.evaluate(v, report())
    assert row(p, "C3")["status"] == "unknown" and row(p, "C5")["status"] == "unknown"


@pytest.mark.parametrize("bad", [{"C3": "maybe"}, {"C7": "yes"}, {"C1": "yes"}, {"C2": "no"}, {"C3": True}, "yes", ["C3"]])
def test_malformed_attestations_are_rejected(bad):
    with pytest.raises(ValueError):
        scan.evaluate(view(), report(), bad)


def test_unanswered_is_accepted_as_not_answered():
    assert scan.check_attestations({"C3": "unanswered", "C4": "yes"}) == {"C4": "yes"}


def test_the_model_probability_decides_nothing():
    a, b = report(), report()
    b["probability"], b["interval"] = 0.01, [0.0, 0.05]
    assert scan.evaluate(view(**HIGH), a)["criteria"] == scan.evaluate(view(**HIGH), b)["criteria"]


def test_gaps_match_unknown_criteria_one_to_one_and_values_are_untouched():
    v = view(velorin_index=150.0)
    before = [dict(e) for e in v["panel"]]
    p = scan.evaluate(v, report(tremor="possible"), {"C4": "yes"})
    unknown = [r["id"] for r in p["criteria"] if r["status"] == "unknown"]
    assert [g["criterion"] for g in p["gaps"]] == unknown
    assert v["panel"] == before


def test_a_value_above_the_policy_threshold_but_inside_the_labs_range_counts_and_says_so():
    p = scan.evaluate(view(velorin_index=125.0, tarnic_acid=365.0), report())
    assert row(p, "C1")["status"] == "met"
    text = next(e for e in p["evidence"] if e["id"] == "lab:velorin_index")["text"]
    assert text == "Velorin index 125 mg/dL (above the policy threshold of 120 mg/dL; lab reference range 70 to 130 mg/dL)"


def test_a_value_exactly_at_the_threshold_does_not_count():
    p = scan.evaluate(view(velorin_index=120.0, tarnic_acid=360.0, dorrin_ratio=1.25), report())
    assert row(p, "C1")["status"] == "unmet"  # none of the three is strictly above, and all are reported


def test_a_lab_above_its_reference_range_is_judged_only_by_the_policy_threshold():
    # 135 is above the lab's reference high (130) and above 120; 119 is inside the range and below the threshold
    assert row(scan.evaluate(view(velorin_index=135.0, tarnic_acid=380.0), report()), "C1")["status"] == "met"
    assert row(scan.evaluate(view(velorin_index=119.0, tarnic_acid=380.0, dorrin_ratio=1.0), report()), "C1")["status"] == "unmet"


def test_the_evidence_never_calls_a_lab_high_or_low_and_ratio_has_no_unit():
    p = scan.evaluate(view(velorin_index=90.0, tarnic_acid=500.0, dorrin_ratio=1.3), report())
    texts = [e["text"] for e in p["evidence"] if e["id"].startswith("lab:")]
    assert texts and not any(w in t for t in texts for w in (" high", " low"))
    ratio = next(t for t in texts if t.startswith("Dorrin"))
    assert ratio == "Dorrin ratio 1.3 (above the policy threshold of 1.25; lab reference range 0.6 to 1.4)"
