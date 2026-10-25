import json
import re
from collections import Counter

import pytest

from data_gen.cli import main
from data_gen.cohort import generate_cohort
from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.dataset_io import read_dataset
from data_gen.llm.checks import offline_errors
from data_gen.llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache
from data_gen.llm.run import generate_llm, plan_all, run_and_write
from data_gen.validate import dataset_errors, pair_group_errors, unique_patients

from llm_oracle import OracleLLM

CFG = GenConfig(note_source="llm", seed=7, n_train=60, n_test=24, n_per_adversarial_type=4,
                llm=LLMConfig(matched_pairs=6))


@pytest.fixture(scope="module")
def items():
    return plan_all(CFG)


def client(oracle, tmp_path, max_calls=100000, max_spend=1000.0):
    return CachedClient(oracle, DiskCache(tmp_path / "cache.jsonl"), Budget(max_calls, max_spend, 0.10, 0.50), "1")


# --- 6.1 matched-pair planning -----------------------------------------------------------------------------

def test_plan_counts_and_unique_ids(items):
    by = Counter(i.split for i in items)
    assert abs(by["train"] - 60) <= 1
    assert by["test"] == (24 - 6) + 6 * 4  # 18 single-setting patients + 6 patients written four times
    assert by["adversarial"] == 7 * 4
    ids = [i.record_id for i in items]
    assert len(set(ids)) == len(ids)


def test_pair_groups_cover_every_setting_with_setting_blind_ids(items):
    groups = {}
    for i in items:
        if i.pair_group:
            groups.setdefault(i.pair_group, []).append(i)
    assert len(groups) == 6
    for group, members in groups.items():
        assert sorted(m.planned.plan.style for m in members) == sorted(LLM_SETTINGS)
        assert sorted(m.record_id for m in members) == [f"{group}-m{k}" for k in (1, 2, 3, 4)]
        assert all(m.split == "test" for m in members)
        for m in members:
            assert not any(s in m.record_id for s in LLM_SETTINGS)
    first_slot_settings = {next(m.planned.plan.style for m in ms if m.record_id.endswith("-m1")) for ms in groups.values()}
    assert len(first_slot_settings) >= 2, "the id suffix must not map to a fixed setting"


def test_members_share_the_patient_and_the_lab_panel(items):
    groups = {}
    for i in items:
        if i.pair_group:
            groups.setdefault(i.pair_group, []).append(i)
    for members in groups.values():
        assert len({m.patient.patient_id for m in members}) == 1
        assert len({frozenset(m.planned.missing) for m in members}) == 1
        assert len({tuple(sorted(m.planned.panel_overrides.items())) for m in members}) == 1
        assert len({m.planned.plan.render_seed for m in members}) == 4  # independent noise per member


def test_planning_is_deterministic_and_offline(items):
    again = plan_all(CFG)
    assert [i.record_id for i in again] == [i.record_id for i in items]
    assert [i.planned.plan for i in again] == [i.planned.plan for i in items]


def test_plan_all_requires_the_llm_source():
    with pytest.raises(ValueError, match="llm"):
        plan_all(GenConfig(n_train=10, n_test=5))


# --- generation with a fake LLM ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def result(items, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("run")
    return generate_llm(CFG, client(OracleLLM(items), tmp), items)


def test_generated_dataset_validates(result):
    assert dataset_errors(result.by_split, min_per_type=4) == []
    assert pair_group_errors(result.by_split) == []
    assert result.pair_groups == 6 and result.pair_groups_dropped == 0


def test_every_accepted_note_passes_the_offline_checks(result):
    for recs in result.by_split.values():
        for r in recs:
            assert offline_errors(r.input.note, r.plan) == [], r.patient_id
            assert r.schema_version == "2" and r.plan_version == "2"


def test_pair_members_have_identical_ground_truth_and_distinct_text(result):
    groups = {}
    for r in result.by_split["test"]:
        if r.pair_group:
            groups.setdefault(r.pair_group, []).append(r)
    assert len(groups) == 6
    for members in groups.values():
        assert len({m.ground_truth.model_dump_json() for m in members}) == 1
        assert len({m.input.note for m in members}) == 4
        assert len({m.style for m in members}) == 4


def test_pooled_metrics_can_deduplicate_by_pair_group(result):
    test = result.by_split["test"]
    assert len(test) == 18 + 24
    unique = unique_patients(test)
    assert len(unique) == 24
    assert len({r.pair_group or r.patient_id for r in test}) == 24


def test_ground_truth_matches_the_template_cohort(result):
    cohort = {p.patient_id: p for p in generate_cohort(CFG) if p.split != "adversarial"}
    for r in result.by_split["train"] + result.by_split["test"]:
        base = re.sub(r"-m\d$", "", r.patient_id)
        p = cohort[base]
        assert r.ground_truth.labs == p.labs and r.ground_truth.flags == p.flags
        assert (r.ground_truth.label, r.ground_truth.true_probability) == (p.label, p.true_probability)


def test_injection_records_carry_the_catalog_text(result):
    inj = [r for r in result.by_split["adversarial"] if "prompt_injection" in r.tag_types()]
    assert len(inj) == 4
    for r in inj:
        assert r.plan.injection.text in r.input.note


# --- 5.2 caps: no partial split --------------------------------------------------------------------------------------

def test_cap_halts_the_run_with_nothing_written_and_the_cache_intact(items, tmp_path):
    out = tmp_path / "data"
    cap = client(OracleLLM(items), tmp_path, max_calls=15)
    with pytest.raises(BudgetExceeded, match="call cap reached: 15 of 15"):
        run_and_write(CFG, cap, out, items)
    assert not out.exists()  # no partial split was written
    cached_lines = (tmp_path / "cache.jsonl").read_text().splitlines()
    assert len(cached_lines) == 15 and all(json.loads(l)["k"] for l in cached_lines)
    # a continued run reuses the completed notes: the first 15 calls cost nothing
    resumed_oracle = OracleLLM(items)
    resumed = client(resumed_oracle, tmp_path, max_calls=100000)
    run_and_write(CFG, resumed, out, items)
    assert resumed.hits >= 15 and out.exists()


# --- end to end: written files and manifest ----------------------------------------------------------------------------

def test_run_and_write_records_provenance(items, tmp_path):
    out = tmp_path / "data"
    c = client(OracleLLM(items), tmp_path)
    run_and_write(CFG, c, out, items)
    by_split, manifest = read_dataset(out)
    assert manifest["note_source"] == "llm" and manifest["plan_version"] == "2" and manifest["schema_version"] == "2"
    llm = manifest["llm"]
    assert llm["model_id"] == "claude-haiku-5-5" and llm["prompt_version"] == "2"
    assert llm["pair_groups_planned"] == 6 and llm["pair_groups_dropped"] == 0
    assert manifest["llm_calls"] == c.misses and manifest["llm_calls"] > 0
    assert llm["excluded"] == {} and manifest["excluded_records"] == 0
    assert set(llm["prompt_text_hashes"]) == set(LLM_SETTINGS)
    assert sum(manifest["splits"]["train"]["styles"].values()) == len(by_split["train"])
    assert manifest["splits"]["test"]["n"] == 42 and manifest["splits"]["test"]["n_unique_patients"] == 24
    assert main(["validate", "--data", str(out)]) == 0


def test_a_second_run_makes_zero_calls_and_is_byte_identical(items, tmp_path):
    first = tmp_path / "a"
    c1 = client(OracleLLM(items), tmp_path)
    run_and_write(CFG, c1, first, items)
    silent = OracleLLM(items)
    c2 = client(silent, tmp_path)
    second = tmp_path / "b"
    run_and_write(CFG, c2, second, items)
    assert silent.calls == [] and c2.misses == 0
    for name in ("train.jsonl", "test.jsonl", "adversarial.jsonl"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


# --- exclusions and incomplete groups ---------------------------------------------------------------------------------------

def test_an_excluded_member_removes_its_whole_pair_group(items, tmp_path):
    res = generate_llm(CFG, client(OracleLLM(items, fail_setting="ai_scribe"), tmp_path), items)
    assert res.pair_groups_dropped == 6 and res.pair_groups == 0
    assert not any(r.pair_group for r in res.by_split["test"])
    assert pair_group_errors(res.by_split) == []
    assert not any(r.style == "ai_scribe" for recs in res.by_split.values() for r in recs)
    d = res.tally.as_dict()
    assert set(d["excluded"]) == {"ai_scribe"} and d["excluded"]["ai_scribe"] > 6
    assert res.tally.exclusion_rate("ai_scribe") == 1.0 and res.tally.exclusion_rate("shorthand") == 0.0
    assert res.stats["pair_groups_dropped"] == 6
