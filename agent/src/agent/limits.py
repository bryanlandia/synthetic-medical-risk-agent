"""Choose the counters: the shared store when it is configured, else the process-local ones."""

from __future__ import annotations

import time
from typing import Callable, Protocol

import httpx

from .config import Settings
from .ratelimit import RateLimiter
from .spend import SpendCounter
from .store import RedisRateLimiter, RedisSpend, RestStore


class Limiter(Protocol):
    def check(self, client: str) -> float | None:
        """Record a request: None, or the seconds the client must wait."""


class Spend(Protocol):
    def exhausted(self) -> bool: ...
    def add(self, usd: float) -> float: ...
    def total_today(self) -> float: ...


def build_limits(settings: Settings, clock: Callable[[], float] = time.time,
                 client: httpx.Client | None = None) -> tuple[Limiter, Spend]:
    """The rate limiter and the spend counter for these settings (``client`` lets a test stand in for the store)."""
    if settings.store_url:
        store = RestStore(settings.store_url, settings.store_token or "", client=client)
        return (RedisRateLimiter(store, settings.rate_per_minute, settings.rate_per_day, clock),
                RedisSpend(store, settings.daily_budget_usd, clock))
    return (RateLimiter(settings.rate_per_minute, settings.rate_per_day, clock),
            SpendCounter(settings.spend_db, settings.daily_budget_usd, clock))
