import json

import pytest

from data_gen.config import LLMConfig
from data_gen.llm.client import LLMResult, MockClient
from data_gen.llm.extractor import EXTRACTOR_SYSTEM
from data_gen.llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache, cache_key
from data_gen.llm.writer import NoteWriter

from test_llm_writer import GOOD_EXTRACTION, GOOD_NOTE, ScriptedLLM, plan


def cached(inner, tmp_path, *, max_calls=1000, max_spend=100.0, version="1"):
    budget = Budget(max_calls, max_spend, 0.10, 0.50)
    return CachedClient(inner, DiskCache(tmp_path / "cache.jsonl"), budget, version)


def call(client, prompt="p", system="s", model="m", max_tokens=100, nonce=0):
    return client.complete(system=system, prompt=prompt, model=model, max_tokens=max_tokens, nonce=nonce)


# --- 5.1 cache ------------------------------------------------------------------------------------------

def test_second_identical_call_is_a_cache_hit(tmp_path):
    inner = MockClient(responder=lambda s, p: f"out:{p}")
    client = cached(inner, tmp_path)
    first = call(client)
    second = call(client)
    assert first == second and len(inner.calls) == 1
    assert (client.hits, client.misses) == (1, 1)


def test_every_key_component_changes_the_key(tmp_path):
    base = dict(prompt_version="1", system="s", prompt="p", model="m", max_tokens=100, nonce=0)
    keys = {cache_key(**base)}
    for change in ({"prompt_version": "2"}, {"system": "s2"}, {"prompt": "p2"}, {"model": "m2"},
                   {"max_tokens": 200}, {"nonce": 1}):
        keys.add(cache_key(**{**base, **change}))
    assert len(keys) == 7


def test_cache_survives_a_new_process_and_makes_zero_calls(tmp_path):
    first = cached(MockClient(responder=lambda s, p: "alpha"), tmp_path)
    call(first, prompt="a")
    call(first, prompt="b")
    again_inner = MockClient(responder=lambda s, p: "SHOULD NOT BE CALLED")
    again = cached(again_inner, tmp_path)  # a fresh object reading the same file
    assert call(again, prompt="a").text == "alpha" and call(again, prompt="b").text == "alpha"
    assert again_inner.calls == []


def test_truncated_last_line_from_a_crash_is_ignored(tmp_path):
    client = cached(MockClient(responder=lambda s, p: "ok"), tmp_path)
    call(client, prompt="a")
    with (tmp_path / "cache.jsonl").open("a") as f:
        f.write('{"k": "deadbeef", "t": "trunc')  # interrupted mid-write
    again = cached(MockClient(responder=lambda s, p: "new"), tmp_path)
    assert call(again, prompt="a").text == "ok"
    assert len(again.cache.entries) == 1


def test_cache_file_is_deterministic_jsonl(tmp_path):
    def run(path):
        c = CachedClient(MockClient(responder=lambda s, p: f"o-{p}"), DiskCache(path), Budget(99, 99, 0.1, 0.5), "1")
        for p in ("x", "y", "z"):
            call(c, prompt=p)
        return path.read_bytes()

    assert run(tmp_path / "a.jsonl") == run(tmp_path / "b.jsonl")
    lines = (tmp_path / "a.jsonl").read_text().splitlines()
    assert len(lines) == 3 and all(json.loads(l)["k"] for l in lines)


def test_warm_cache_rerun_is_byte_identical_with_zero_calls(tmp_path):
    plans = [plan(), plan(style="ehr_template")]
    cold_llm = ScriptedLLM([GOOD_NOTE, GOOD_NOTE], [GOOD_EXTRACTION, GOOD_EXTRACTION])
    cold = NoteWriter(cached(cold_llm, tmp_path), LLMConfig())
    texts = [cold.write(p).text for p in plans]
    # two writer calls (different setting prompts) and ONE extractor call: both notes are identical text,
    # so the second extractor request is a cache hit
    assert [c["kind"] for c in cold_llm.calls] == ["writer", "extractor", "writer"]
    warm_llm = ScriptedLLM([], [])  # any call would pop from an empty queue and fail
    warm = NoteWriter(cached(warm_llm, tmp_path), LLMConfig())
    assert [warm.write(p).text for p in plans] == texts
    assert warm_llm.calls == []


def test_retries_are_not_replayed_from_the_cache(tmp_path):
    bad = GOOD_NOTE.replace("128.9", "150")
    llm = ScriptedLLM([bad, GOOD_NOTE], [GOOD_EXTRACTION])
    out = NoteWriter(cached(llm, tmp_path), LLMConfig()).write(plan())
    assert out.accepted and out.attempts == 2  # attempt 1 was a cached failure only for nonce 0
    llm2 = ScriptedLLM([], [])
    assert NoteWriter(cached(llm2, tmp_path), LLMConfig()).write(plan()).text == GOOD_NOTE
    assert llm2.calls == []


def test_average_tokens_by_kind(tmp_path):
    c = cached(MockClient(responder=lambda s, p: "x", input_tokens=100, output_tokens=40), tmp_path)
    call(c, system="writer system")
    call(c, system=EXTRACTOR_SYSTEM)
    assert c.cache.average_tokens("writer") == (100, 40) and c.cache.average_tokens("extractor") == (100, 40)
    assert DiskCache(tmp_path / "empty.jsonl").average_tokens("writer") is None


# --- 5.2 caps ----------------------------------------------------------------------------------------------

def test_call_cap_halts_with_a_clear_error_and_keeps_completed_work(tmp_path):
    inner = MockClient(responder=lambda s, p: "ok")
    client = cached(inner, tmp_path, max_calls=3)
    for p in ("a", "b", "c"):
        call(client, prompt=p)
    with pytest.raises(BudgetExceeded, match="call cap reached: 3 of 3"):
        call(client, prompt="d")
    assert len(inner.calls) == 3  # the refused call was never made
    again = cached(MockClient(responder=lambda s, p: "n"), tmp_path, max_calls=3)
    assert [call(again, prompt=p).text for p in ("a", "b", "c")] == ["ok"] * 3  # completed notes stay cached


def test_cache_hits_do_not_count_against_the_cap(tmp_path):
    client = cached(MockClient(responder=lambda s, p: "ok"), tmp_path, max_calls=1)
    call(client, prompt="a")
    for _ in range(10):
        call(client, prompt="a")
    assert client.budget.calls == 1


def test_spend_cap_halts_before_overspending(tmp_path):
    inner = MockClient(responder=lambda s, p: "ok", input_tokens=1_000_000, output_tokens=0)  # $0.10 per call
    client = cached(inner, tmp_path, max_calls=100, max_spend=0.25)
    for p in ("a", "b", "c"):  # 0.10, 0.20, 0.30: the check runs before each call
        call(client, prompt=p)
    with pytest.raises(BudgetExceeded, match="spend cap reached"):
        call(client, prompt="d")
    assert len(inner.calls) == 3 and client.budget.spend_usd == pytest.approx(0.30)


def test_pilot_budget_is_separate_and_smaller():
    cfg = LLMConfig()
    pilot, full = Budget.for_run(cfg, pilot=True), Budget.for_run(cfg)
    assert pilot.max_calls < full.max_calls and pilot.max_spend_usd < full.max_spend_usd
    assert pilot.max_calls == cfg.pilot_max_calls and full.max_spend_usd == cfg.max_spend_usd


def test_budget_charge_uses_configured_prices():
    b = Budget(10, 10.0, 0.10, 0.50)
    b.reserve()  # a call slot is taken before the request is sent...
    b.charge(LLMResult(text="", input_tokens=2_000_000, output_tokens=1_000_000))  # ...and the money after
    assert b.spend_usd == pytest.approx(0.20 + 0.50) and b.calls == 1
