"""Run independent jobs in parallel but hand the results back strictly in order.

Everything that decides what goes into the dataset (which notes are kept, when a setting is stopped,
the counts) consumes results in plan order, so the output is the same at any worker count. Jobs that are
already running when the consumer stops simply finish; their work is cached by the caller.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Iterable, Iterator, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def ordered_parallel(fn: Callable[[T], R], items: Iterable[T], workers: int) -> Iterator[tuple[T, R]]:
    """Yield ``(item, fn(item))`` in item order, with up to ``workers`` calls in flight.

    An exception raised by ``fn`` is re-raised at that item's position. Closing the generator (or leaving
    the consuming loop early) cancels jobs that have not started and waits for the running ones.
    """
    if workers <= 1:
        for item in items:
            yield item, fn(item)
        return
    source = iter(items)
    window: deque[tuple[T, Future]] = deque()
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="notes") as pool:
        try:
            def refill() -> None:
                while len(window) < workers:
                    try:
                        item = next(source)
                    except StopIteration:
                        return
                    window.append((item, pool.submit(fn, item)))

            refill()
            while window:
                item, future = window.popleft()
                result = future.result()  # raises here, in order
                refill()
                yield item, result
        finally:
            for _, future in window:
                future.cancel()
