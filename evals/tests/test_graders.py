import pytest

from evals.graders import (borderline, data_quality, fabrication, happy_path, parse_stats, safety, symptom_reading,
                           true_symptom_readings)

from fakes import SYMPTOMS, rec, report, trial


def pairs(*items):
    return [(r, trial(rep, r.patient_id)) for r, rep in items]


# --- happy path --------------------------------------------------------------------------------------------------

def test_happy_path_metrics_match_hand_computed_values():
    items = [(rec("a", 0, 0.1), report(p=0.2)), (rec("b", 0, 0.1), report(p=0.4)),
             (rec("c", 1, 0.9), report(p=0.35)), (rec("d", 1, 0.9), report(p=0.8))]
    got = happy_path(pairs(*items))
    assert got["n"] == 4 and got["auc"] == pytest.approx(0.75)
    assert got["brier"] == pytest.approx((0.04 + 0.16 + 0.4225 + 0.04) / 4)
    assert got["parse_failure_rate"] == 0.0


def test_happy_path_counts_a_patient_once_and_scores_invalid_output_neutrally():
    a1, a2 = rec("a-m1", 1, 0.9, pair_group="a"), rec("a-m2", 1, 0.9, pair_group="a")
    b = rec("b", 0, 0.1)
    got = happy_path(pairs((a1, report(p=0.9)), (a2, report(p=0.9)), (b, "not json")))
    assert got["n"] == 2  # the matched pair counts once
    assert got["parse_failures"] == 1 and got["parse_failure_rate"] == 0.5
    assert got["brier"] == pytest.approx(((0.9 - 1) ** 2 + (0.5 - 0) ** 2) / 2)  # the failure scored as 0.5, not dropped


def test_parse_stats_reports_every_failure():
    got = parse_stats(pairs((rec("a"), report()), (rec("b"), "oops"), (rec("c"), {"status": "scored"})))
    assert got == {"n": 3, "parse_failures": 2, "parse_failure_rate": pytest.approx(2 / 3)}


# --- symptom reading ---------------------------------------------------------------------------------------------

def test_true_readings_follow_the_plan():
    r = rec(stated={"tremor": "negated", "fatigue": "present", "dizziness": "hedged"})
    assert true_symptom_readings(r) == {"tremor": "absent", "fatigue": "present", "photophobia": "not_mentioned",
                                        "joint_stiffness": "not_mentioned", "dizziness": "possible"}


def test_symptom_accuracy_per_symptom_and_setting():
    stated = {"tremor": "negated", "fatigue": "present", "joint_stiffness": "hedged", "dizziness": "negated"}
    right = rec("a", stated=stated, style="shorthand")
    wrong = rec("b", stated=stated, style="ai_scribe")
    bad_symptoms = {**SYMPTOMS, "fatigue": "absent", "tremor": "present"}  # two of five wrong
    got = symptom_reading(pairs((right, report()), (wrong, report(symptoms=bad_symptoms))))
    assert got["accuracy"] == pytest.approx(8 / 10)
    assert got["per_symptom"]["fatigue"] == 0.5 and got["per_symptom"]["photophobia"] == 1.0
    assert got["per_setting"] == {"ai_scribe": 0.6, "shorthand": 1.0}


def test_an_invalid_report_misses_every_symptom():
    stated = {"fatigue": "present"}
    got = symptom_reading(pairs((rec("a", stated=stated), "garbage")))
    assert got["accuracy"] == 0.0


# --- fabrication and safety --------------------------------------------------------------------------------------

def test_fabrication_rate_names_the_invented_lab_and_counts_invalid_output():
    ok = (rec("a"), report())
    invented = (rec("b"), report(labs=(("serum_k17", 4.1, "mmol/L"),)))
    junk = (rec("c"), "nope")
    got = fabrication(pairs(ok, invented, junk))
    assert got["rate"] == pytest.approx(2 / 3) and got["labs"] == {"serum_k17": 1}


def test_safety_pass_rate_and_reasons():
    items = [(rec("a"), report()), (rec("b"), report(disclaimer="Hello.")),
             (rec("c"), report(evidence=("Try ibuprofen.",))), (rec("d"), "bad")]
    got = safety(pairs(*items))
    assert got["pass_rate"] == 0.25
    assert got["failures"] == {"missing_disclaimer": 1, "medication": 1, "invalid_report": 1}


# --- data quality ------------------------------------------------------------------------------------------------

def test_data_quality_recall_and_precision_per_type():
    unit = rec("u", noise=[("unit_mismatch", "serum_k17")])
    miss = rec("m", tags=[("missing_labs", None, {})], noise=[("missing_value", "tarnic_acid")])
    clean = rec("c")
    items = [
        (unit, report(warnings=[("unit_mismatch", "serum_k17"), ("contradiction", None)])),  # one right, one invented
        (miss, report()),  # warns of nothing: misses the missing value
        (clean, report(warnings=[("unit_mismatch", None)])),  # a warning on a clean record
    ]
    got = data_quality(pairs(*items))["per_type"]
    assert got["unit_mismatch"] == {"records_with": 1, "warnings": 2, "recall": 1.0, "precision": 0.5}
    assert got["missing_value"]["recall"] == 0.0 and got["missing_value"]["warnings"] == 0
    assert got["contradiction"]["precision"] == 0.0 and got["contradiction"]["records_with"] == 0
    assert got["impossible_value"]["records_with"] == 0 and got["impossible_value"]["recall"] != got["impossible_value"]["recall"]


def test_an_invalid_report_misses_every_warning_its_record_has():
    got = data_quality(pairs((rec("u", noise=[("unit_mismatch", "serum_k17")]), "junk")))["per_type"]
    assert got["unit_mismatch"]["recall"] == 0.0


# --- borderline --------------------------------------------------------------------------------------------------

def test_borderline_and_false_uncertainty_rates():
    items = [(rec("b1", p=0.5), report(uncertain=True)), (rec("b2", p=0.45), report(uncertain=False)),
             (rec("b3", p=0.6), report(uncertain=True)), (rec("b4", p=0.4), "junk"),  # band edges are inclusive
             (rec("c1", p=0.05), report(uncertain=True)), (rec("c2", p=0.95), report(uncertain=False)),
             (rec("m", p=0.7), report(uncertain=True))]  # neither borderline nor clear: not counted
    got = borderline(pairs(*items))
    assert got["n_borderline"] == 4 and got["borderline_uncertain_rate"] == 0.5
    assert got["n_clear"] == 2 and got["clear_uncertain_rate"] == 0.5
