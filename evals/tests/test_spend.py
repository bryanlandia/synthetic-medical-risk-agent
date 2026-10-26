import json
import os

import pytest
from data_gen.llm.client import MockClient
from data_gen.llm.gateway import Budget

from evals.devsplit import dev_ids
from evals.prompt_system import PromptSystem, estimate_calls
from evals.runner import run_suites
from evals.systems import scored_report

CALLS = []


def responder(system, prompt):
    view = json.loads(prompt)
    CALLS.append(view["patient_id"])
    return json.dumps(scored_report(view, 0.3, uncertain=False))


def build(tmp_path, max_calls=10_000, max_spend=100.0):
    client = MockClient(responder=responder, input_tokens=900, output_tokens=300)
    budget = Budget(max_calls, max_spend, 2.0, 10.0)
    return PromptSystem("mock-frontier", "You score fictional records.", "claude-sonnet-5-5", client,
                        tmp_path / "cache.jsonl", budget), client


@pytest.fixture(autouse=True)
def clear_calls():
    CALLS.clear()


def dev_records(dataset, n):
    ids = set(dev_ids(dataset))
    return [r for r in dataset.by_split["train"] if r.patient_id in ids][:n]


def test_the_estimate_needs_no_key_and_makes_no_call(dataset, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    system, client = build(tmp_path)
    est = estimate_calls(system, dev_records(dataset, 40), trials=3)
    assert est.calls == 120 and est.cached == 0 and est.uncached == 120 and est.cost_usd > 0 and not est.measured
    assert client.calls == [] and CALLS == [] and not (tmp_path / "cache.jsonl").exists()


def test_the_estimate_counts_the_injection_counterfactual_runs(dataset, tmp_path):
    system, _ = build(tmp_path)
    records = dataset.by_split["adversarial"]
    plain = estimate_calls(system, records)
    pairs = estimate_calls(system, records, injection_pairs=True)
    assert pairs.calls == plain.calls + 60  # one extra run for each of the 60 injection records


def test_a_run_pays_once_and_a_rerun_is_free_and_identical(dataset, tmp_path):
    records = dev_records(dataset, 30)
    system, client = build(tmp_path)
    first = run_suites(dataset, system, "dev", suites=["happy_path"], limit=30, log_dir=tmp_path / "l1")
    paid = len(client.calls)
    assert paid == 30 and system.client.misses == 30
    second_system, second_client = build(tmp_path)  # a new process: the cache comes from disk
    second = run_suites(dataset, second_system, "dev", suites=["happy_path"], limit=30, log_dir=tmp_path / "l2")
    assert len(second_client.calls) == 0 and second_system.client.misses == 0 and second_system.client.hits == 30
    key = lambda run: sorted((r["record_id"], r["raw_output"]) for r in run.rows)  # noqa: E731
    assert key(first) == key(second)
    est = estimate_calls(second_system, records)
    assert est.cached == est.calls == 30 and est.cost_usd == 0 and est.measured is True


def test_a_changed_prompt_starts_fresh_and_trials_have_their_own_cache_entries(dataset, tmp_path):
    system, client = build(tmp_path)
    run_suites(dataset, system, "dev", suites=["happy_path"], limit=10, trials=2, log_dir=tmp_path / "l")
    assert len(client.calls) == 20  # two trials of ten records, each its own call
    other = PromptSystem("mock-frontier", "A different prompt.", "claude-sonnet-5-5", client, tmp_path / "cache.jsonl",
                         Budget(1000, 100.0, 2.0, 10.0))
    assert other.version != system.version
    run_suites(dataset, other, "dev", suites=["happy_path"], limit=10, log_dir=tmp_path / "l2")
    assert len(client.calls) == 30


def test_the_call_cap_halts_safely_and_a_higher_cap_makes_only_the_missing_calls(dataset, tmp_path):
    system, client = build(tmp_path, max_calls=12)
    run = run_suites(dataset, system, "dev", suites=["happy_path"], limit=30, log_dir=tmp_path / "l1")
    assert "call cap reached" in run.stopped and len(client.calls) == 12
    assert len(run.sink.trials["happy_path"]) == 12 and len(run.rows) == 12  # finished trials are kept and saved
    assert len((tmp_path / "cache.jsonl").read_text().splitlines()) == 12  # every paid result is cached
    resumed, resumed_client = build(tmp_path, max_calls=1000)
    again = run_suites(dataset, resumed, "dev", suites=["happy_path"], limit=30, log_dir=tmp_path / "l2")
    assert again.stopped is None and len(resumed_client.calls) == 18  # only the missing ones
    assert len(again.rows) == 30


def test_the_spend_cap_halts_too(dataset, tmp_path):
    per_call = (900 * 2.0 + 300 * 10.0) / 1_000_000
    system, client = build(tmp_path, max_spend=per_call * 5.5)
    run = run_suites(dataset, system, "dev", suites=["happy_path"], limit=30, log_dir=tmp_path / "l")
    assert "spend cap reached" in run.stopped and 5 < len(client.calls) <= 7


def test_the_key_is_not_written_anywhere(dataset, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret-value-1234567890")
    system, _ = build(tmp_path)
    run = run_suites(dataset, system, "dev", suites=["happy_path"], limit=5, log_dir=tmp_path / "l")
    blob = (tmp_path / "cache.jsonl").read_text() + json.dumps(run.rows)
    assert "sk-ant-test-secret" not in blob
