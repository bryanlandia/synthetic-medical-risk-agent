import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_gen.builder import assemble_record, plan_for
from data_gen.cli import main
from data_gen.cohort import build_patient
from data_gen.config import LLM_SETTINGS, GenConfig
from data_gen.dataset_io import dump_record, read_dataset
from data_gen.rule import calibrated_intercept
from data_gen.schema import Record
from data_gen.validate import dataset_errors, pair_group_errors, record_errors

DATA = Path(__file__).resolve().parents[1] / "data"
CFG = GenConfig(note_source="llm", seed=5, n_train=50, n_test=20)


def llm_member(setting, index=3, pid=None, group="P5-000003", note=None, split="test", patient=None):
    patient = patient or build_patient(CFG.seed, index, calibrated_intercept(CFG.target_prevalence))
    planned = plan_for(CFG, patient, None)
    planned.missing, planned.panel_overrides = set(), {}  # a pair shares one lab panel
    planned.plan = planned.plan.model_copy(update={"style": setting})
    return assemble_record(
        CFG, patient, split, None, planned, note or f"note written as {setting}",
        patient_id=pid or f"{group}-m{LLM_SETTINGS.index(setting) + 1}", pair_group=group,
    )


def good_group():
    return [llm_member(s) for s in LLM_SETTINGS]


# --- version coherence -----------------------------------------------------------------------

def test_schema_2_records_are_valid_and_carry_pair_group():
    rec = llm_member("shorthand")
    assert rec.schema_version == "2" and rec.plan_version == "2" and rec.pair_group == "P5-000003"
    assert json.loads(dump_record(rec))["pair_group"] == "P5-000003"
    assert Record.model_validate_json(dump_record(rec)) == rec


def test_schema_1_dump_has_no_pair_group_key():
    cohort = read_dataset(DATA)[0]["train"][:5]
    for rec in cohort:
        assert rec.schema_version == "1" and rec.plan_version == "1"
        assert "pair_group" not in json.loads(dump_record(rec))


def test_inconsistent_versions_are_rejected():
    rec = llm_member("shorthand")
    base = rec.model_dump()
    for change in (
        {"schema_version": "1"},  # plan v2 needs schema 2
        {"schema_version": "3"},  # unknown schema
        {"plan_version": "1"},  # does not match the plan
    ):
        with pytest.raises(ValidationError):
            Record(**{**base, **change})
    v1 = read_dataset(DATA)[0]["train"][0].model_dump()
    with pytest.raises(ValidationError):
        Record(**{**v1, "pair_group": "x"})  # pair_group needs schema 2


# --- committed template dataset still validates --------------------------------------------------

def test_committed_template_dataset_still_validates(capsys):
    assert main(["validate", "--data", str(DATA)]) == 0
    by_split, _ = read_dataset(DATA)
    assert dataset_errors(by_split) == []


# --- LLM records and pair groups -------------------------------------------------------------------

def test_llm_records_pass_structural_validation():
    for rec in good_group():
        assert record_errors(rec) == []


def test_good_pair_group_has_no_errors():
    assert pair_group_errors({"test": good_group()}) == []


def test_pair_group_must_have_one_record_per_setting():
    errs = pair_group_errors({"test": good_group()[:3]})
    assert any("one record per setting" in e for e in errs)


def test_pair_group_rejects_differing_ground_truth():
    group = good_group()
    other = replace(build_patient(CFG.seed, 3, calibrated_intercept(CFG.target_prevalence)), label=1)
    if group[0].ground_truth.label == 1:
        other = replace(other, label=0)
    group[1] = llm_member(group[1].style, patient=other)
    assert any("ground truth differs" in e for e in pair_group_errors({"test": group}))


def test_pair_group_rejects_identical_text_and_wrong_split():
    same = [llm_member(s, note="identical") for s in LLM_SETTINGS]
    assert any("identical text" in e for e in pair_group_errors({"test": same}))
    train = [llm_member(s, split="train") for s in LLM_SETTINGS]
    assert any("test split" in e for e in pair_group_errors({"train": train}))


def test_pair_group_rejects_differing_panels():
    group = good_group()
    panel = list(group[2].input.panel)
    panel[0] = panel[0].model_copy(update={"value": None})
    group[2] = group[2].model_copy(update={"input": group[2].input.model_copy(update={"panel": panel})})
    assert any("panel differs" in e for e in pair_group_errors({"test": group}))


def test_record_ids_must_not_reveal_the_setting():
    leaky = llm_member("ai_scribe", pid="P5-000003-ai_scribe")
    assert any("reveals its setting" in e for e in record_errors(leaky))
    assert all(s not in r.patient_id for r in good_group() for s in LLM_SETTINGS)


def test_dataset_ids_stay_unique_across_pair_members():
    group = good_group()
    assert len({r.patient_id for r in group}) == 4
    errs = dataset_errors({"train": [], "test": group, "adversarial": []}, min_per_type=0)
    assert not any("not unique" in e for e in errs)
