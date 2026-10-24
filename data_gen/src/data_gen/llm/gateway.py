"""Cache and spending caps in front of any LLM client. Safe to call from several worker threads.

``CachedClient`` has the same ``complete`` interface as a client, so the note writer is unaware of it.
Results are appended to a JSONL file the moment they arrive (an interrupted run loses nothing), a cache
hit makes no call and costs nothing, and a paid call is refused once a configured cap is reached.

Under concurrency the call cap is exact: a call slot is reserved before the request is sent. The spend
cap is checked before each call and charged after it, so it can overshoot by at most the calls that are
in flight (a few hundredths of a dollar at Haiku prices).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..config import LLMConfig
from .client import LLMClient, LLMResult
from .extractor import EXTRACTOR_SYSTEM

log = logging.getLogger("data_gen.llm")
SLOW_CALL_SECONDS = 30.0


class BudgetExceeded(RuntimeError):
    """A configured call or spend cap was reached; the run must stop. Completed work stays cached."""


@dataclass
class Budget:
    max_calls: int
    max_spend_usd: float
    price_input_per_mtok: float
    price_output_per_mtok: float
    calls: int = 0  # paid calls started (reserved), including any still in flight
    spend_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @classmethod
    def for_review(cls, cfg: LLMConfig) -> "Budget":
        return cls(max_calls=cfg.reviewer_max_calls, max_spend_usd=cfg.reviewer_max_spend_usd,
                   price_input_per_mtok=cfg.reviewer_price_input_per_mtok,
                   price_output_per_mtok=cfg.reviewer_price_output_per_mtok)

    @classmethod
    def for_run(cls, cfg: LLMConfig, *, pilot: bool = False) -> "Budget":
        return cls(
            max_calls=cfg.pilot_max_calls if pilot else cfg.max_calls,
            max_spend_usd=cfg.pilot_max_spend_usd if pilot else cfg.max_spend_usd,
            price_input_per_mtok=cfg.price_input_per_mtok,
            price_output_per_mtok=cfg.price_output_per_mtok,
        )

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"call cap reached: {self.calls} of {self.max_calls} calls made. Completed notes are cached; "
                "raise llm.max_calls (or llm.pilot_max_calls) to continue."
            )
        if self.spend_usd >= self.max_spend_usd:
            raise BudgetExceeded(
                f"spend cap reached: about ${self.spend_usd:.2f} of ${self.max_spend_usd:.2f} spent. Completed "
                "notes are cached; raise llm.max_spend_usd (or llm.pilot_max_spend_usd) to continue."
            )

    def reserve(self) -> None:
        """Take one call slot, or raise. Atomic, so concurrent workers can never exceed the call cap."""
        with self._lock:
            self.check()
            self.calls += 1

    def charge(self, result: LLMResult) -> None:
        with self._lock:
            self.spend_usd += (
                result.input_tokens * self.price_input_per_mtok + result.output_tokens * self.price_output_per_mtok
            ) / 1_000_000


@dataclass
class DiskCache:
    """Append-only JSONL cache. A truncated last line from a crash is ignored."""

    path: Path
    entries: dict[str, dict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    self.entries[entry["k"]] = entry
                except (json.JSONDecodeError, KeyError):
                    continue

    def get(self, key: str) -> LLMResult | None:
        e = self.entries.get(key)
        if e is None:
            return None
        return LLMResult(text=e["t"], input_tokens=e["i"], output_tokens=e["o"], stop_reason=e.get("s"))

    def put(self, key: str, kind: str, result: LLMResult) -> None:
        entry = {"k": key, "kind": kind, "t": result.text, "i": result.input_tokens,
                 "o": result.output_tokens, "s": result.stop_reason}
        with self._lock:
            self.entries[key] = entry
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(entry, sort_keys=True, ensure_ascii=True) + "\n")
                f.flush()

    def compact(self) -> int:
        """Rewrite the file sorted by key without duplicates, so a committed cache is deterministic no matter
        in which order concurrent workers finished. Returns the number of entries."""
        with self._lock:
            if not self.entries:
                return 0
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text("".join(
                json.dumps(self.entries[k], sort_keys=True, ensure_ascii=True) + "\n" for k in sorted(self.entries)))
            os.replace(tmp, self.path)
            return len(self.entries)

    def average_tokens(self, kind: str) -> tuple[float, float] | None:
        rows = [e for e in list(self.entries.values()) if e.get("kind") == kind]
        if not rows:
            return None
        return (sum(e["i"] for e in rows) / len(rows), sum(e["o"] for e in rows) / len(rows))


def cache_key(prompt_version: str, system: str, prompt: str, model: str, max_tokens: int, nonce: int) -> str:
    blob = json.dumps([prompt_version, system, prompt, model, max_tokens, nonce], ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class CachedClient:
    """Wraps a client with a cache and a budget. Same ``complete`` signature as an ``LLMClient``."""

    def __init__(self, inner: LLMClient, cache: DiskCache, budget: Budget, prompt_version: str,
                 kind: str | None = None):
        self.inner, self.cache, self.budget, self.prompt_version = inner, cache, budget, prompt_version
        self.kind = kind  # label for cached entries and logs; by default writer or extractor
        self.hits = 0
        self.misses = 0
        self._count_lock = threading.Lock()

    def complete(
        self, *, system: str, prompt: str, model: str, max_tokens: int, nonce: int = 0
    ) -> LLMResult:
        key = cache_key(self.prompt_version, system, prompt, model, max_tokens, nonce)
        kind = self.kind or ("extractor" if system == EXTRACTOR_SYSTEM else "writer")
        cached = self.cache.get(key)
        if cached is not None:
            with self._count_lock:
                self.hits += 1
            log.debug("cache hit: %s call (nonce %d)", kind, nonce)
            return cached
        self.budget.reserve()  # refuse BEFORE spending; reserves the call slot atomically
        log.debug("calling the API: %s, nonce %d, up to %d output tokens", kind, nonce, max_tokens)
        started = time.monotonic()
        result = self.inner.complete(system=system, prompt=prompt, model=model, max_tokens=max_tokens, nonce=nonce)
        seconds = time.monotonic() - started
        self.budget.charge(result)
        with self._count_lock:
            self.misses += 1
        self.cache.put(key, kind, result)
        log.info("api call %d: %s nonce=%d in=%d out=%d stop=%s %.1fs (spend ~$%.3f)", self.budget.calls, kind,
                 nonce, result.input_tokens, result.output_tokens, result.stop_reason, seconds, self.budget.spend_usd)
        if seconds > SLOW_CALL_SECONDS:
            log.warning("slow API call: %s took %.0fs (the client times out at its limit and retries)", kind, seconds)
        if result.stop_reason == "max_tokens":
            log.warning("%s response hit the output limit (%d tokens) and was cut off; raise llm.max_tokens "
                        "if this repeats", kind, max_tokens)
        return result
