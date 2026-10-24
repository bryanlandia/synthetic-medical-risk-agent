import threading
import time

import pytest

from data_gen.config import LLMConfig
from data_gen.llm.pool import ordered_parallel


def test_results_come_back_in_item_order_even_when_jobs_finish_out_of_order():
    def job(n):
        time.sleep(0.03 if n % 2 == 0 else 0.0)  # even items are slower than the odd ones after them
        return n * n

    out = list(ordered_parallel(job, range(20), workers=6))
    assert out == [(n, n * n) for n in range(20)]


def test_sequential_mode_is_the_same_thing_with_one_worker():
    assert list(ordered_parallel(lambda n: n + 1, range(5), workers=1)) == [(n, n + 1) for n in range(5)]
    assert list(ordered_parallel(lambda n: n, [], workers=4)) == []


def test_never_more_than_the_worker_limit_in_flight_and_calls_do_overlap():
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def job(_):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.02)
        with lock:
            state["now"] -= 1

    list(ordered_parallel(job, range(40), workers=5))
    assert 2 <= state["peak"] <= 5


def test_parallelism_actually_saves_time():
    def job(_):
        time.sleep(0.05)

    t0 = time.monotonic()
    list(ordered_parallel(job, range(16), workers=8))
    assert time.monotonic() - t0 < 16 * 0.05 / 2  # far below the 0.8 s a sequential run would need


def test_an_exception_is_raised_at_its_position_and_stops_the_rest():
    started = []

    def job(n):
        started.append(n)
        if n == 3:
            raise RuntimeError("boom")
        time.sleep(0.01)
        return n

    seen = []
    with pytest.raises(RuntimeError, match="boom"):
        for item, _ in ordered_parallel(job, range(200), workers=4):
            seen.append(item)
    assert seen == [0, 1, 2]  # nothing after the failing item is handed out
    assert len(started) < 200  # pending work was cancelled, not run to the end


def test_leaving_the_loop_early_cancels_pending_work_but_lets_running_jobs_finish():
    finished = []

    def job(n):
        time.sleep(0.02)
        finished.append(n)
        return n

    gen = ordered_parallel(job, range(500), workers=4)
    for item, _ in gen:
        if item == 5:
            break
    gen.close()
    assert len(finished) < 500
    assert set(range(6)) <= set(finished)  # everything up to the stopping point completed


def test_concurrency_setting_is_bounded():
    assert LLMConfig().concurrency == 8
    for bad in (0, -1, 33):
        with pytest.raises(ValueError):
            LLMConfig(concurrency=bad)
    assert LLMConfig(concurrency=1).concurrency == 1 and LLMConfig(concurrency=32).concurrency == 32
