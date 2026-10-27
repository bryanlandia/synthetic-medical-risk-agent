import json

from evals import demo_patients
from evals.devsplit import dev_ids
from evals.messages import render_message
from evals.records import input_view

FORBIDDEN_KEYS = {"ground_truth", "true_probability", "label", "flags", "labs_true", "noise", "tags", "plan"}


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _committed():
    return json.loads(demo_patients.DEFAULT_OUT.read_text())


def test_every_demo_patient_is_a_dev_record(dataset):
    dev = set(dev_ids(dataset))
    patients = _committed()["patients"]
    assert len(patients) == len(demo_patients.RULES)
    assert all(p["patient_id"] in dev and p["split"] == "dev" for p in patients)


def test_every_message_is_what_the_harness_renders(dataset):
    for p in _committed()["patients"]:
        assert p["message"] == render_message(input_view(dataset.record(p["patient_id"]))), p["patient_id"]


def test_the_file_carries_no_ground_truth():
    data = _committed()
    assert not FORBIDDEN_KEYS & set(_walk(data))
    for p in data["patients"]:
        assert set(p) == {"slug", "title", "look_for", "patient_id", "split", "chart", "message"}
        assert set(p["chart"]) == {"labs", "note"}


def test_the_chart_matches_the_message(dataset):
    for p in _committed()["patients"]:
        stated = [f"- {lab['name']} ({lab['abbr']}): {lab['value']:g} {lab['unit']}" for lab in p["chart"]["labs"] if lab["value"] is not None]
        assert p["message"] == "\n".join(["Labs:", *stated, "", "Note:", p["chart"]["note"]])


def test_the_committed_file_is_what_the_command_writes(dataset):
    assert demo_patients.DEFAULT_OUT.read_text() == demo_patients.text(dataset)


def test_the_demo_patients_show_what_they_say_they_show(dataset):
    kinds = {p["slug"]: {n.type for n in dataset.record(p["patient_id"]).noise} for p in _committed()["patients"]}
    assert not kinds["routine"] and {"unit_mismatch", "missing_value"} <= kinds["unit-and-missing"] and "contradiction" in kinds["contradiction"]
