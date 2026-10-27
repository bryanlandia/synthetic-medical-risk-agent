"""A sliding-window rate limiter held in memory, per process.

The deployment is one instance, so a per-process limiter is enough; a second instance would have its own counts (stated in
the README). The clock is injected so the windows can be tested without waiting.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

MINUTE, DAY = 60.0, 86_400.0


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, clock: Callable[[], float] = time.time):
        self.per_minute, self.per_day, self.clock = per_minute, per_day, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client: str) -> float | None:
        """Record a request and return None, or the seconds to wait if the client is over a limit (the request is not recorded)."""
        now = self.clock()
        with self._lock:
            hits = self._hits[client]
            while hits and now - hits[0] >= DAY:
                hits.popleft()
            recent = [t for t in hits if now - t < MINUTE]
            if len(recent) >= self.per_minute:
                return max(1.0, MINUTE - (now - recent[0]))
            if len(hits) >= self.per_day:
                return max(1.0, DAY - (now - hits[0]))
            hits.append(now)
            return None
