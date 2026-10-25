import json
import math

import pytest

from data_gen.cli import main
from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.llm.client import API_KEY_ENV
from data_gen.llm.estimate import estimate, exceeds_caps
from data_gen.llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache
from data_gen.llm.pilot import pilot_items
from data_gen.llm.run import generate_llm, plan_all

from llm_oracle import OracleLLM

CFG = GenConfig(note_source="llm", seed=7, n_train=80, n_test=24, n_per_adversarial_type=4,
                llm=LLMConfig(matched_pairs=6, pilot_per_setting=5))


@pytest.fixture(scope="module")
def items():
    return plan_all(CFG)


def run_to_cache(items, path, max_calls=100000):
    c = CachedClient(OracleLLM(items), DiskCache(path), Budget(max_calls, 1000.0, 0.1, 0.5), CFG.llm.prompt_version)
    try:
        generate_llm(CFG, c, items)
    except BudgetExceeded:
        pass
    return c


# --- counts ----------------------------------------------------------------------------------------------------

def test_empty_cache_counts_a_writer_and_an_extractor_call_per_note(items):
    est = estimate(CFG, items)
    assert est.notes == len(items)
    assert est.first_attempt_calls == 2 * len(items) and est.cached_calls == 0
    assert est.expected_retry_calls == math.ceil(0.25 * est.first_attempt_calls)
    assert est.uncached_calls == est.first_attempt_calls + est.expected_retry_calls
    assert sum(est.per_setting.values()) == est.notes and set(est.per_setting) == set(LLM_SETTINGS)


def test_matched_pair_notes_are_included(items):
    pair_notes = sum(1 for i in items if i.pair_group)
    assert pair_notes == 6 * 4
    assert estimate(CFG, items).notes == len(items) > CFG.n_train + CFG.n_test + 7 * 4  # pairs add notes


def test_pilot_estimate_counts_only_the_pilot_sample(items):
    pilot = pilot_items(CFG, items)
    assert len(pilot) == 5 * 4
    assert {i.planned.plan.style for i in pilot} == set(LLM_SETTINGS)
    assert all(i.split == "train" and i.case is None and i.pair_group is None for i in pilot)
    est = estimate(CFG, pilot)
    assert est.notes == 20 and est.first_attempt_calls == 40
    assert est.cost_usd < estimate(CFG, items).cost_usd


def test_pilot_items_are_items_of_the_full_run(items):
    full_ids = {i.record_id for i in items}
    assert {i.record_id for i in pilot_items(CFG, items)} <= full_ids


def test_cost_scales_with_prices_and_notes(items):
    base = estimate(CFG, items)
    pricey = estimate(CFG.model_copy(update={"llm": LLMConfig(
        matched_pairs=6, pilot_per_setting=5, price_input_per_mtok=1.0, price_output_per_mtok=5.0)}), items)
    assert pricey.cost_usd == pytest.approx(base.cost_usd * 10, rel=0.01)
    assert estimate(CFG, items[:50]).cost_usd < base.cost_usd


# --- cache awareness ----------------------------------------------------------------------------------------------

def test_a_complete_cache_makes_the_estimate_zero(items, tmp_path):
    run_to_cache(items, tmp_path / "c.jsonl")
    est = estimate(CFG, items, DiskCache(tmp_path / "c.jsonl"))
    assert est.first_attempt_calls == 0 and est.cost_usd == 0 and est.expected_retry_calls == 0
    assert est.cached_calls == 2 * len(items)


def test_a_partial_cache_shrinks_the_estimate(items, tmp_path):
    full = estimate(CFG, items)
    run_to_cache(items, tmp_path / "c.jsonl", max_calls=30)
    part = estimate(CFG, items, DiskCache(tmp_path / "c.jsonl"))
    assert part.cached_calls + part.first_attempt_calls == 2 * len(items)  # every call is cached or pending
    assert 0 < part.cached_calls and part.first_attempt_calls < full.first_attempt_calls
    assert part.cost_usd < full.cost_usd


def test_measured_token_averages_replace_assumptions(items, tmp_path):
    cache = DiskCache(tmp_path / "m.jsonl")
    from data_gen.llm.client import LLMResult
    for n in range(12):
        cache.put(f"w{n}", "writer", LLMResult("t", 1000, 500))
        cache.put(f"x{n}", "extractor", LLMResult("t", 200, 50))
    est = estimate(CFG, items[:40], cache, retry_rate=0.0)
    assert est.assumptions["measured_writer_tokens_used"] and est.assumptions["measured_extractor_tokens_used"]
    assert est.input_tokens == 40 * (1000 + 200) and est.output_tokens == 40 * (500 + 50)
    assert estimate(CFG, items[:40], DiskCache(tmp_path / "none.jsonl")).assumptions["measured_writer_tokens_used"] is False


def test_few_cache_entries_are_not_trusted(items, tmp_path):
    cache = DiskCache(tmp_path / "m.jsonl")
    from data_gen.llm.client import LLMResult
    for n in range(3):
        cache.put(f"w{n}", "writer", LLMResult("t", 1000, 500))
    assert estimate(CFG, items[:10], cache).assumptions["measured_writer_tokens_used"] is False


def test_cap_warnings(items):
    small = CFG.model_copy(update={"llm": LLMConfig(max_calls=10, max_spend_usd=0.001)})
    warnings = exceeds_caps(small, estimate(small, items))
    assert len(warnings) == 2 and "max_calls" in warnings[0] and "max_spend_usd" in warnings[1]
    assert exceeds_caps(CFG, estimate(CFG, items)) == []


# --- the CLI -----------------------------------------------------------------------------------------------------------

SMALL = ["--note-source", "llm", "--seed", "7", "--n-train", "80", "--n-test", "24", "--n-per-adversarial-type", "4"]


@pytest.fixture
def cfg_file(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"llm": {"matched_pairs": 6, "pilot_per_setting": 5}}))
    return ["--config", str(f)]


def test_estimate_cli_needs_no_key_and_never_builds_a_client(monkeypatch, tmp_path, cfg_file, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)

    def boom(*a, **k):
        raise AssertionError("estimate must not create an API client")

    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", boom)
    assert main(["estimate", "--cache", str(tmp_path / "c.jsonl"), *SMALL, *cfg_file]) == 0
    out = capsys.readouterr().out
    assert "full run" in out and "estimated cost: $" in out and "assumed" in out


def test_estimate_cli_json_and_pilot(tmp_path, cfg_file, capsys):
    assert main(["estimate", "--json", "--pilot", "--cache", str(tmp_path / "c.jsonl"), *SMALL, *cfg_file]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["notes"] == 20 and data["uncached_calls"] > 0 and data["cost_usd"] > 0


def test_estimate_cli_rejects_the_template_source(capsys):
    assert main(["estimate", "--note-source", "template"]) == 2
    assert "LLM note source" in capsys.readouterr().err


def test_llm_generate_refuses_to_spend_without_yes(monkeypatch, tmp_path, cfg_file, capsys):
    monkeypatch.setenv(API_KEY_ENV, "k")
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    out = tmp_path / "out"
    assert main(["generate", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *SMALL, *cfg_file]) == 4
    assert "--yes" in capsys.readouterr().err and not out.exists()


def test_llm_generate_without_a_key_stops_before_any_call(monkeypatch, tmp_path, cfg_file, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    out = tmp_path / "out"
    assert main(["generate", "--yes", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *SMALL, *cfg_file]) == 2
    assert API_KEY_ENV in capsys.readouterr().err and not out.exists()


def test_llm_generate_with_yes_writes_a_valid_dataset(monkeypatch, tmp_path, cfg_file, capsys, items):
    oracle = OracleLLM(items)
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: oracle)
    out = tmp_path / "out"
    assert main(["generate", "--yes", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *SMALL, *cfg_file]) == 0
    assert "paid calls" in capsys.readouterr().out
    assert main(["validate", "--data", str(out)]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["note_source"] == "llm" and manifest["llm_calls"] == len(oracle.calls)


def test_llm_generate_stops_cleanly_at_the_cap(monkeypatch, tmp_path, capsys, items):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"llm": {"matched_pairs": 6, "pilot_per_setting": 5, "max_calls": 12}}))
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items))
    out = tmp_path / "out"
    assert main(["generate", "--yes", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *SMALL, "--config", str(f)]) == 3
    err = capsys.readouterr().err
    assert "call cap reached" in err and "nothing was written" in err and not out.exists()
    assert len((tmp_path / "c.jsonl").read_text().splitlines()) == 12
