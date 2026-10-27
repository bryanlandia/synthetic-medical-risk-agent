"""A shared store for the spend total and the request counts, spoken to over HTTPS (Upstash's Redis REST API).

The local counters (``SpendCounter`` in SQLite, ``RateLimiter`` in memory) are right for one long-lived process. A platform that
runs several short-lived instances needs the counts in one place, or the daily cap and the rate limits would not hold.
Any store failure raises ``StoreError`` and the caller refuses the request: the limits fail closed.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import httpx

MINUTE, DAY = 60, 86_400


class StoreError(RuntimeError):
    """The store could not be reached or answered with an error; never carries a credential."""


class RestStore:
    def __init__(self, url: str, token: str, timeout: float = 3.0, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"authorization": f"Bearer {token}"}

    def pipeline(self, commands: Sequence[Sequence[Any]]) -> list[Any]:
        """Run commands in order and return each one's result."""
        try:
            response = self._client.post(f"{self.url}/pipeline", json=[[str(a) for a in c] for c in commands], headers=self._headers)
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise StoreError(f"store request failed: {type(exc).__name__}") from None
        if not isinstance(rows, list) or len(rows) != len(commands) or any("error" in r for r in rows):
            raise StoreError("store returned an error")
        return [r.get("result") for r in rows]


class RedisSpend:
    """The day's spend (UTC) in one key, shared by every instance."""

    def __init__(self, store: RestStore, daily_cap_usd: float, clock: Callable[[], float] = time.time):
        self.store, self.cap, self.clock = store, daily_cap_usd, clock

    def _key(self) -> str:
        return "spend:" + datetime.fromtimestamp(self.clock(), tz=timezone.utc).strftime("%Y-%m-%d")

    def total_today(self) -> float:
        (value,) = self.store.pipeline([["GET", self._key()]])
        return float(value) if value is not None else 0.0

    def remaining(self) -> float:
        return max(0.0, self.cap - self.total_today())

    def exhausted(self) -> bool:
        return self.total_today() >= self.cap

    def add(self, usd: float) -> float:
        key = self._key()
        total, _ = self.store.pipeline([["INCRBYFLOAT", key, repr(float(usd))], ["EXPIRE", key, 2 * DAY]])
        return float(total)


class RedisRateLimiter:
    """Per-client counts in fixed windows (a minute, a day). A client may send up to twice the per-minute limit across a window
    boundary; the daily dollar cap is the real bound on spend."""

    def __init__(self, store: RestStore, per_minute: int, per_day: int, clock: Callable[[], float] = time.time):
        self.store, self.per_minute, self.per_day, self.clock = store, per_minute, per_day, clock

    def check(self, client: str) -> float | None:
        """Record a request and return None, or the seconds to wait if the client is over a limit (the request is not recorded)."""
        now = self.clock()
        minute, day = int(now // MINUTE), int(now // DAY)
        kmin, kday = f"rate:min:{client}:{minute}", f"rate:day:{client}:{day}"
        in_minute, _, in_day, _ = self.store.pipeline(
            [["INCR", kmin], ["EXPIRE", kmin, 2 * MINUTE], ["INCR", kday], ["EXPIRE", kday, DAY + 3600]])
        if in_minute > self.per_minute or in_day > self.per_day:
            self.store.pipeline([["DECR", kmin], ["DECR", kday]])
            end = (minute + 1) * MINUTE if in_minute > self.per_minute else (day + 1) * DAY
            return float(max(1, math.ceil(end - now)))
        return None
