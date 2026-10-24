import threading
import time

import pytest

from data_gen.cli import main
from data_gen.config import GenConfig, LLMConfig
from data_gen.llm.client import LLMCallError, LLMResult
from data_gen.llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache
from data_gen.llm.pilot import run_pilot
from data_gen.llm.run import generate_llm, plan_all, run_and_write
from data_gen.llm.writer import RATE_LIMIT_RETRIES, NoteWriter

from llm_oracle import OracleLLM
from test_llm_writer import GOOD_EXTRACTION, GOOD_NOTE, ScriptedLLM, plan


def cfg_with(workers: int, **llm) -> GenConfig:
    return GenConfig(note_source="llm", seed=7, n_train=240, n_test=24, n_per_adversarial_type=4,
                     llm=LLMConfig(matched_pairs=6, pilot_per_setting=10, concurrency=workers, **llm))


@pytest.fixture(scope="module")
def items():
    return plan_all(cfg_with(1))


def client(oracle, tmp_path, name="c.jsonl", max_calls=1_000_000):
    return CachedClient(oracle, DiskCache(tmp_path / name), Budget(max_calls, 1000.0, 0.1, 0.5), "1")


class SlowOracle(OracleLLM):
    """An oracle whose calls take time and which records how many were in flight at once."""

    def __init__(self, *a, delay=0.01, **k):
        super().__init__(*a, **k)
        self.delay, self.now, self.peak, self._lock = delay, 0, 0, threading.Lock()

    def complete(self, **kw):
        with self._lock:
            self.now += 1
            self.peak = max(self.peak, self.now)
        try:
            time.sleep(self.delay)
            return super().complete(**kw)
        finally:
            with self._lock:
                self.now -= 1


# --- the output does not depend on the worker count --------------------------------------------------------------

def test_full_run_is_identical_at_one_and_eight_workers(items, tmp_path):
    runs = {}
    for w in (1, 8):
        cfg = cfg_with(w)
        runs[w] = generate_llm(cfg, client(OracleLLM(items), tmp_path, f"w{w}.jsonl"), items)
    one, eight = runs[1], runs[8]
    for split in one.by_split:
        assert [r.model_dump_json() for r in one.by_split[split]] == [r.model_dump_json() for r in eight.by_split[split]]
    assert one.tally.as_dict() == eight.tally.as_dict()
    assert (one.pair_groups, one.pair_groups_dropped) == (eight.pair_groups, eight.pair_groups_dropped)


def test_written_files_are_byte_identical_at_any_worker_count(items, tmp_path):
    for w in (1, 4):
        run_and_write(cfg_with(w), client(OracleLLM(items), tmp_path, f"b{w}.jsonl"), tmp_path / f"out{w}", items)
    for name in ("train.jsonl", "test.jsonl", "adversarial.jsonl"):
        assert (tmp_path / "out1" / name).read_bytes() == (tmp_path / "out4" / name).read_bytes()
    import json
    m1 = json.loads((tmp_path / "out1" / "manifest.json").read_text())
    m4 = json.loads((tmp_path / "out4" / "manifest.json").read_text())
    assert m1["config_hash"] == m4["config_hash"], "the worker count must not change the config hash"
    assert m1["splits"] == m4["splits"]


def test_pilot_sample_and_exclusions_do_not_depend_on_the_worker_count(items, tmp_path):
    flaky = {}
    for w in (1, 8):
        oracle = OracleLLM(items, fail_setting="ehr_template", fail_every=4)  # deterministic per distinct prompt
        flaky[w] = run_pilot(cfg_with(w), client(oracle, tmp_path, f"p{w}.jsonl"), items)
    assert [n.record_id for n in flaky[1].notes] == [n.record_id for n in flaky[8].notes]
    assert flaky[1].tally.as_dict()["excluded"] == flaky[8].tally.as_dict()["excluded"]
    assert flaky[1].aborted == flaky[8].aborted == {} and flaky[1].short == flaky[8].short


def test_early_stop_decisions_do_not_depend_on_the_worker_count(items, tmp_path):
    res = {w: run_pilot(cfg_with(w), client(OracleLLM(items, fail_setting="copy_forward"), tmp_path, f"a{w}.jsonl"), items)
           for w in (1, 8)}
    assert res[1].aborted == res[8].aborted == {"copy_forward": 1.0}
    assert res[1].tally.attempted("copy_forward") == res[8].tally.attempted("copy_forward")


# --- real parallelism, with a hard ceiling -------------------------------------------------------------------------------

def test_calls_overlap_up_to_the_worker_limit(items, tmp_path):
    oracle = SlowOracle(items, delay=0.01)
    generate_llm(cfg_with(8), client(oracle, tmp_path), items[:120])
    assert 2 <= oracle.peak <= 8


def test_sequential_runs_never_overlap(items, tmp_path):
    oracle = SlowOracle(items, delay=0.002)
    generate_llm(cfg_with(1), client(oracle, tmp_path), items[:40])
    assert oracle.peak == 1


def test_eight_workers_are_much_faster_than_one(items, tmp_path):
    def timed(w):
        t0 = time.monotonic()
        generate_llm(cfg_with(w), client(SlowOracle(items, delay=0.01), tmp_path, f"t{w}.jsonl"), items[:60])
        return time.monotonic() - t0

    assert timed(8) < timed(1) / 2.5


# --- caps stay exact -----------------------------------------------------------------------------------------------------------

def test_call_cap_is_exact_with_eight_workers(items, tmp_path):
    oracle = SlowOracle(items, delay=0.005)
    cap = client(oracle, tmp_path, max_calls=25)
    with pytest.raises(BudgetExceeded, match="call cap reached: 25 of 25"):
        run_and_write(cfg_with(8), cap, tmp_path / "out", items)
    assert not (tmp_path / "out").exists()  # nothing written to a split
    assert cap.misses == 25 and cap.budget.calls == 25  # not one call more
    assert len((tmp_path / "c.jsonl").read_text().splitlines()) == 25  # every paid result was cached


def test_concurrent_cache_writes_never_corrupt_the_file(items, tmp_path):
    generate_llm(cfg_with(8), client(OracleLLM(items), tmp_path), items[:150])
    import json
    lines = (tmp_path / "c.jsonl").read_text().splitlines()
    parsed = [json.loads(l) for l in lines]  # raises if any line is torn
    assert len(parsed) == len({p["k"] for p in parsed}) and len(parsed) > 100


# --- rate limits ---------------------------------------------------------------------------------------------------------------------

class Throttled(ScriptedLLM):
    def __init__(self, *a, rate_limits=0, **k):
        super().__init__(*a, **k)
        self.remaining = rate_limits
        self.attempts_seen = 0

    def complete(self, **kw):
        self.attempts_seen += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise LLMCallError("429 rate limit", retryable=True, rate_limited=True)
        return super().complete(**kw)


def test_rate_limits_back_off_exponentially_without_using_up_attempts():
    waits = []
    llm = Throttled([GOOD_NOTE], [GOOD_EXTRACTION], rate_limits=3)
    out = NoteWriter(llm, LLMConfig(), sleep=waits.append).write(plan())
    assert out.accepted and out.attempts == 1 and out.failures == []  # the note's attempt count is unchanged
    assert len(waits) == 3
    assert 0.5 <= waits[0] <= 1.0 and 1.0 <= waits[1] <= 2.0 and 2.0 <= waits[2] <= 4.0  # 1s, 2s, 4s with jitter


def test_backoff_is_bounded_and_then_fails_the_attempt():
    waits = []
    llm = Throttled([GOOD_NOTE] * 3, [GOOD_EXTRACTION], rate_limits=10_000)
    out = NoteWriter(llm, LLMConfig(max_attempts=1), sleep=waits.append).write(plan())
    assert not out.accepted and out.failures == [["call_error"]]
    assert len(waits) == RATE_LIMIT_RETRIES and max(waits) <= 32.0


def test_errors_that_are_not_rate_limits_are_not_backed_off():
    waits = []
    llm = ScriptedLLM([LLMCallError("overloaded?", retryable=True), GOOD_NOTE], [GOOD_EXTRACTION])
    out = NoteWriter(llm, LLMConfig(), sleep=waits.append).write(plan())
    assert out.accepted and out.failures == [["call_error"]] and waits == []


def test_rate_limit_signal_comes_from_the_client():
    from test_llm_client import FakeSDK, response
    from data_gen.llm.client import API_KEY_ENV, AnthropicClient
    import os

    os.environ[API_KEY_ENV] = "k"
    try:
        for exc, limited in ((FakeSDK.RateLimitError("429"), True), (FakeSDK.APIStatusError("x", 529), True),
                             (FakeSDK.APIStatusError("x", 429), True), (FakeSDK.APIStatusError("x", 503), False),
                             (FakeSDK.APIStatusError("x", 400), False)):
            with pytest.raises(LLMCallError) as info:
                AnthropicClient(sdk=FakeSDK(raises=exc)).complete(system="s", prompt="p", model="m", max_tokens=5)
            assert info.value.rate_limited is limited
    finally:
        del os.environ[API_KEY_ENV]


# --- cache compaction (9.3) -------------------------------------------------------------------------------------------------------------

def test_compaction_sorts_the_cache_and_keeps_every_entry(items, tmp_path):
    c = client(OracleLLM(items), tmp_path)
    generate_llm(cfg_with(8), c, items[:120])
    before = dict(c.cache.entries)
    n = c.cache.compact()
    import json
    keys = [json.loads(l)["k"] for l in (tmp_path / "c.jsonl").read_text().splitlines()]
    assert keys == sorted(keys) and n == len(keys) == len(before)
    assert DiskCache(tmp_path / "c.jsonl").entries == before  # nothing lost or changed
    assert not (tmp_path / "c.jsonl.tmp").exists()


def test_two_runs_with_different_worker_counts_give_the_same_compacted_cache(items, tmp_path):
    for w in (1, 8):
        c = client(OracleLLM(items), tmp_path, f"k{w}.jsonl")
        generate_llm(cfg_with(w), c, items[:150])
        c.cache.compact()
    assert (tmp_path / "k1.jsonl").read_bytes() == (tmp_path / "k8.jsonl").read_bytes()


def test_cli_compacts_the_cache_after_a_successful_run(monkeypatch, tmp_path, items, capsys):
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items))
    import json
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"llm": {"matched_pairs": 6, "pilot_per_setting": 10, "concurrency": 8}}))
    args = ["--note-source", "llm", "--seed", "7", "--n-train", "240", "--n-test", "24",
            "--n-per-adversarial-type", "4", "--config", str(f)]
    assert main(["generate", "--yes", "--quiet", "--out", str(tmp_path / "out"), "--cache", str(tmp_path / "c.jsonl"), *args]) == 0
    keys = [json.loads(l)["k"] for l in (tmp_path / "c.jsonl").read_text().splitlines()]
    assert keys == sorted(keys)
