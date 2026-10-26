import pytest
from data_gen.llm.client import MockClient
from data_gen.llm.gateway import Budget

from evals.frontier import (DEV_MODEL, FINAL_MODEL, STAGES, Stage, StageOverCap, build_frontier_system, check_cap,
                            estimate_stage, make_budget, stage_for, stage_records)
from evals.records import input_view
from evals.report import SCHEMA_PATH  # noqa: F401


def system(tmp_path, model=FINAL_MODEL, stage="test"):
    return build_frontier_system("v1", model, MockClient(lambda s, p: ""), tmp_path / "c.jsonl",
                                 make_budget(model, STAGES[stage]))


def test_estimate_counts_match_a_hand_count_of_the_dataset(dataset, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = system(tmp_path)
    injected = sum(1 for r in dataset.by_split["adversarial"] if any(t.type == "prompt_injection" for t in r.tags))
    assert injected == 60
    assert estimate_stage(s, dataset, STAGES["dev"]).calls == 500
    assert estimate_stage(s, dataset, STAGES["test"]).calls == len(dataset.by_split["test"]) == 1438
    assert estimate_stage(s, dataset, STAGES["adversarial"]).calls == len(dataset.by_split["adversarial"]) + injected
    pairs = [r for r in dataset.by_split["test"] if r.pair_group]
    assert estimate_stage(s, dataset, STAGES["trials"]).calls == 3 * len(pairs) == 2028
    assert not (tmp_path / "c.jsonl").exists() and s.client.inner.calls == []  # no call, no key needed


def test_records_in_several_suites_are_one_call(dataset):
    ids = [r.patient_id for r in stage_records(dataset, STAGES["test"])]
    assert len(ids) == len(set(ids)) == 1438


def test_trials_after_the_test_stage_only_pay_for_the_new_trials(dataset, tmp_path):
    s = system(tmp_path, stage="trials")
    for r in stage_records(dataset, STAGES["trials"]):
        s.cache.put(s.key_for(input_view(r), 0), "eval", __import__("data_gen.llm.client", fromlist=["LLMResult"]).LLMResult("{}", 1800, 600))
    est = estimate_stage(s, dataset, STAGES["trials"])
    assert est.calls == 2028 and est.cached == 676 and est.uncached == 1352 and est.measured is True  # the cache now holds measurements
    check_cap(est, STAGES["trials"])  # 1352 calls and about $15: inside the caps


def test_the_sonnet_stages_fit_their_caps_and_a_stage_above_a_cap_is_refused(dataset, tmp_path):
    s = system(tmp_path)
    for name in ("dev", "test", "adversarial"):
        check_cap(estimate_stage(s, dataset, STAGES[name]), STAGES[name])
    tight = Stage("test", "test", None, 1, False, max_calls=100, max_usd=100.0)
    with pytest.raises(StageOverCap, match="calls to make"):
        check_cap(estimate_stage(s, dataset, tight), tight)
    cheap = Stage("test", "test", None, 1, False, max_calls=10_000, max_usd=1.0)
    with pytest.raises(StageOverCap, match="estimated"):
        check_cap(estimate_stage(s, dataset, cheap), cheap)


def test_haiku_dev_passes_cost_under_a_dollar(dataset, tmp_path):
    assert estimate_stage(system(tmp_path, DEV_MODEL), dataset, STAGES["dev"]).cost_usd < 1.0


def test_stage_for_maps_runs_to_stages():
    assert stage_for("dev", None, 1).name == "dev" and stage_for("adversarial", None, 1).name == "adversarial"
    assert stage_for("test", ["consistency"], 3).name == "trials" and stage_for("test", None, 1).name == "test"
    for bad in (("test", None, 3), ("adversarial", None, 2)):
        with pytest.raises(ValueError):
            stage_for(*bad)


def test_the_budget_carries_the_models_prices_and_the_stage_caps():
    b = make_budget(FINAL_MODEL, STAGES["test"])
    assert (b.price_input_per_mtok, b.price_output_per_mtok, b.max_calls) == (2.0, 10.0, STAGES["test"].max_calls)
    assert make_budget(DEV_MODEL, STAGES["dev"]).price_input_per_mtok == 0.10
