import json
import threading
import time

from data_gen.llm.client import LLMCallError, LLMResult
from data_gen.llm.gateway import Budget

from evals.devsplit import dev_ids
from evals.prompt_system import CALL_ERROR_PREFIX, RATE_LIMIT_RETRIES, PromptSystem
from evals.report import parse_report
from evals.runner import run_suites
from evals.systems import scored_report


class Slow:
    """A deterministic client (the answer depends only on the record) that records how many calls overlap."""

    def __init__(self, delay=0.005, errors=None):
        self.delay, self.now, self.peak, self.calls = delay, 0, 0, 0
        self.errors = errors or []  # exceptions to raise first, in order
        self._lock = threading.Lock()

    def complete(self, *, system, prompt, model, max_tokens, nonce=0):
        with self._lock:
            self.calls += 1
            self.now += 1
            self.peak = max(self.peak, self.now)
            err = self.errors.pop(0) if self.errors else None
        try:
            time.sleep(self.delay)
            if err:
                raise err
            view = json.loads(prompt)
            p = 0.1 + (sum(map(ord, view["patient_id"])) % 80) / 100 + nonce / 1000
            n = 300 + sum(map(ord, view["patient_id"])) % 50
            return LLMResult(json.dumps(scored_report(view, p, uncertain=False)), 900, n, "tool_use")
        finally:
            with self._lock:
                self.now -= 1


def system(tmp_path, client, name="c.jsonl", max_calls=100_000, **kw):
    return PromptSystem("t", "You score fictional records.", "claude-sonnet-5-5", client, tmp_path / name,
                        Budget(max_calls, 1000.0, 2.0, 10.0), **kw)


def run(dataset, tmp_path, workers, name, **kw):
    s = system(tmp_path, Slow(), f"{name}.jsonl")
    r = run_suites(dataset, s, "dev", suites=["happy_path"], limit=40, trials=2, log_dir=tmp_path / name,
                   workers=workers, **kw)
    return s, r


def stable(rows):
    return [{k: v for k, v in row.items() if k != "latency_s"} for row in rows]


def test_results_usage_and_cache_are_identical_at_one_and_eight_workers(dataset, tmp_path):
    (s1, r1), (s8, r8) = run(dataset, tmp_path, 1, "w1"), run(dataset, tmp_path, 8, "w8")
    assert stable(r1.rows) == stable(r8.rows) and len(r1.rows) == 80
    assert sum(r["input_tokens"] + r["output_tokens"] for r in r1.rows) == sum(
        r["input_tokens"] + r["output_tokens"] for r in r8.rows) > 0
    s1.cache.compact(), s8.cache.compact()
    assert (tmp_path / "w1.jsonl").read_bytes() == (tmp_path / "w8.jsonl").read_bytes()


def test_calls_overlap_up_to_the_worker_limit_and_never_beyond(dataset, tmp_path):
    for workers, low in ((8, 2), (1, 1)):
        client = Slow(delay=0.01)
        run_suites(dataset, system(tmp_path, client, f"p{workers}.jsonl"), "dev", suites=["happy_path"], limit=40,
                   log_dir=tmp_path / f"l{workers}", workers=workers)
        assert low <= client.peak <= workers


def test_the_call_cap_is_exact_with_eight_workers(dataset, tmp_path):
    client = Slow()
    s = system(tmp_path, client, max_calls=15)
    r = run_suites(dataset, s, "dev", suites=["happy_path"], limit=40, log_dir=tmp_path / "l", workers=8)
    assert "call cap reached" in r.stopped and client.calls == 15
    assert len((tmp_path / "c.jsonl").read_text().splitlines()) == 15  # every paid result was cached
    assert len(r.rows) == 15


def test_rate_limits_back_off_without_failing_the_trial(dataset, tmp_path):
    waits = []
    client = Slow(delay=0, errors=[LLMCallError("429", True, rate_limited=True)] * 3)
    out = system(tmp_path, client, sleep=waits.append).run_call({"patient_id": "a1", "panel": [], "note": ""}, 0)
    assert parse_report(out.text).ok and len(waits) == 3
    assert 0.5 <= waits[0] <= 1.0 and 1.0 <= waits[1] <= 2.0 and 2.0 <= waits[2] <= 4.0


def test_endless_rate_limits_and_other_errors_are_counted_failures_that_are_not_cached(dataset, tmp_path):
    waits = []
    s = system(tmp_path, Slow(delay=0, errors=[LLMCallError("429", True, rate_limited=True)] * 50), sleep=waits.append)
    out = s.run_call({"patient_id": "a1", "panel": [], "note": ""}, 0)
    assert out.text.startswith(CALL_ERROR_PREFIX) and not parse_report(out.text).ok
    assert len(waits) == RATE_LIMIT_RETRIES and max(waits) <= 32.0
    other = system(tmp_path, Slow(delay=0, errors=[LLMCallError("auth", False)]), "o.jsonl")
    assert other.run_call({"patient_id": "a1", "panel": [], "note": ""}, 0).text.startswith(CALL_ERROR_PREFIX)
    assert not (tmp_path / "o.jsonl").exists()  # a failed call is retried on rerun, not replayed


def test_trials_of_one_record_keep_their_own_index_under_concurrency(dataset, tmp_path):
    _, r = run(dataset, tmp_path, 8, "idx")
    by_record = {}
    for row in r.rows:
        by_record.setdefault(row["record_id"], []).append(row["trial_index"])
    assert all(v == [0, 1] for v in by_record.values())
