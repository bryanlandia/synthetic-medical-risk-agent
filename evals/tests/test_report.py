import json

import pytest

from evals.report import SCHEMA_PATH, parse_report, schema_text

SYMPTOMS = {"tremor": "absent", "fatigue": "present", "photophobia": "not_mentioned", "joint_stiffness": "possible",
            "dizziness": "absent"}


def scored(**over):
    base = {"status": "scored", "probability": 0.31, "uncertain": False, "symptoms": SYMPTOMS,
            "labs_used": [{"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}],
            "data_quality": [{"type": "missing_value", "lab": "serum_k17"}],
            "evidence": ["Velorin index near the middle of its range."],
            "disclaimer": "This is not medical advice."}
    base.update(over)
    return base


def declined(**over):
    base = {"status": "declined", "reason": "treatment_request", "message": "I cannot give treatment advice."}
    base.update(over)
    return base


def errors(obj):
    result = parse_report(obj)
    assert not result.ok, "expected an invalid report"
    return " | ".join(result.errors)


# --- scored reports -------------------------------------------------------------------------------------------

def test_a_valid_scored_report_validates():
    result = parse_report(scored())
    assert result.ok and result.report.probability == 0.31 and result.report.report_version == "1"


def test_an_interval_must_bracket_the_probability():
    assert parse_report(scored(interval=[0.2, 0.4])).ok
    assert "interval" in errors(scored(interval=[0.35, 0.4]))  # lower above the probability
    assert "interval" in errors(scored(interval=[0.2, 0.25]))  # upper below it
    assert "interval" in errors(scored(interval=[-0.1, 0.4]))  # outside [0, 1]


@pytest.mark.parametrize("bad,field", [
    (scored(probability=1.2), "probability"),
    (scored(symptoms={**SYMPTOMS, "tremor": "severe"}), "tremor"),
    (scored(data_quality=[{"type": "typo"}]), "type"),
    (scored(extra_field=1), "extra_field"),
    (scored(symptoms={k: v for k, v in SYMPTOMS.items() if k != "dizziness"}), "symptoms"),
    (scored(labs_used=[{"lab": "glucose", "value": 5.0, "unit": "mmol/L"}]), "lab"),
    (scored(evidence=["x"] * 9), "evidence"),
    (scored(evidence=["y" * 301]), "evidence"),
    (scored(probability=None), "probability"),
    (scored(disclaimer=None), "disclaimer"),
])
def test_out_of_range_and_unknown_content_is_invalid_and_the_error_names_the_field(bad, field):
    assert field in errors(bad)


def test_eight_short_evidence_statements_are_fine():
    assert parse_report(scored(evidence=["z" * 300] * 8)).ok


# --- declined reports --------------------------------------------------------------------------------------------

def test_a_declined_report_is_valid_without_a_probability_and_invalid_with_one():
    assert parse_report(declined()).ok
    assert "probability" in errors(declined(probability=0.5))
    assert "reason" in errors(declined(reason="because"))
    assert "reason" in errors({"status": "declined", "message": "no"})


def test_a_scored_report_cannot_carry_a_decline_reason():
    assert "reason" in errors(scored(reason="out_of_scope"))


# --- parsing ----------------------------------------------------------------------------------------------------------

def test_json_text_is_parsed_and_a_code_fence_is_tolerated():
    text = json.dumps(scored())
    assert parse_report(text).ok and parse_report("```json\n" + text + "\n```").ok
    assert "not valid JSON" in errors("The risk is about 30%.")
    assert "expected a JSON object" in errors("[1, 2]")
    assert not parse_report("Here you go: " + text).ok  # prose around the JSON is not tolerated


# --- the published schema ---------------------------------------------------------------------------------------

def test_the_published_schema_matches_the_model():
    assert SCHEMA_PATH.exists(), "run `evals schema --write`"
    assert SCHEMA_PATH.read_text() == schema_text(), "the model changed: regenerate with `evals schema --write`"
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["additionalProperties"] is False and "status" in schema["properties"]
