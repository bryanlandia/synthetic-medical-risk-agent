"""An API-backed system: a prompt, a model and a client, behind the response cache and the call and spend caps.

Reference systems cost nothing; this is for the systems that do. The cache key is the system version (which hashes
the prompt), the prompt text with the record, and the trial index, so a rerun makes no paid call and a changed
prompt starts fresh. The key is read only from ``ANTHROPIC_API_KEY`` by the client, never stored here.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_gen.llm.client import LLMCallError, LLMClient
from data_gen.llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache, cache_key

from .records import input_view

CHARS_PER_TOKEN = 3.0
ASSUMED_OUTPUT_TOKENS = 450  # until the cache holds measurements
RATE_LIMIT_RETRIES = 6  # 429 and 529 are waited out with backoff; they do not count as a failed trial
CALL_ERROR_PREFIX = "[call error]"


@dataclass(frozen=True)
class CallOutput:
    """One call's text and token usage, returned to the caller instead of kept on the system (safe in threads)."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def prompt_hash(text: str) -> str:
    """Identifies the prompt alone, so the development and final models can be shown to share one prompt."""
    return hashlib.sha256(text.strip().encode()).hexdigest()[:12]


class PromptSystem:
    reference = False
    threaded = True  # ``run_call`` keeps no shared state, so the harness may call it from several threads

    def __init__(self, name: str, system_prompt: str, model: str, client: LLMClient, cache_path: Path | str,
                 budget: Budget, max_tokens: int = 1500, *, sleep=time.sleep, requires_freeze: bool = False):
        self._sleep = sleep
        self.requires_freeze = requires_freeze  # protected splits need the frozen prompt (see protocol.py)
        self.prompt_hash = prompt_hash(system_prompt)
        self.name, self.system_prompt, self.model, self.max_tokens = name, system_prompt, model, max_tokens
        self.version = f"{name}@{hashlib.sha256((system_prompt + model).encode()).hexdigest()[:8]}"
        self.cache = DiskCache(Path(cache_path))
        self.budget = budget
        self.client = CachedClient(client, self.cache, budget, self.version, kind="eval")
        self.trial_index = 0
        self.last_usage: dict[str, int] = {}

    def set_trial(self, index: int) -> None:
        self.trial_index = index

    @staticmethod
    def user_prompt(view: dict[str, Any]) -> str:
        return json.dumps(view, sort_keys=True)

    def run_call(self, view: dict[str, Any], trial_index: int) -> CallOutput:
        """One call for one trial. Rate limits are retried with backoff; any other failed call is returned as
        text that does not parse (a counted failure) and is not cached, so a rerun tries it again."""
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                result = self.client.complete(system=self.system_prompt, prompt=self.user_prompt(view),
                                              model=self.model, max_tokens=self.max_tokens, nonce=trial_index)
                return CallOutput(result.text, result.input_tokens, result.output_tokens)
            except LLMCallError as exc:
                if exc.rate_limited and attempt < RATE_LIMIT_RETRIES:
                    self._sleep(min(32.0, 2.0 ** attempt) * random.uniform(0.5, 1.0))
                    continue
                return CallOutput(f"{CALL_ERROR_PREFIX} {exc}")
        raise AssertionError("unreachable")

    def run(self, view: dict[str, Any]) -> str:
        """The single-threaded form: the trial index set with ``set_trial``, usage left in ``last_usage``."""
        out = self.run_call(view, self.trial_index)
        self.last_usage = {"input_tokens": out.input_tokens, "output_tokens": out.output_tokens}
        return out.text

    def key_for(self, view: dict[str, Any], trial_index: int) -> str:
        return cache_key(self.version, self.system_prompt, self.user_prompt(view), self.model, self.max_tokens, trial_index)


@dataclass
class RunEstimate:
    calls: int
    cached: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    measured: bool

    @property
    def uncached(self) -> int:
        return self.calls - self.cached


def estimate_calls(system: PromptSystem, records: list[Any], trials: int = 1, *, injection_pairs: bool = False,
                   assumed_output_tokens: int = ASSUMED_OUTPUT_TOKENS) -> RunEstimate:
    """Dry run: the calls a run would make, what is already cached, and the cost. Needs no key and makes no call."""
    from .injection import injection_tag, strip_injection

    views: list[dict[str, Any]] = []
    for r in records:
        view = input_view(r)
        views.append(view)
        if injection_pairs and injection_tag(r):
            views.append(strip_injection(view))
    rows = [e for e in system.cache.entries.values() if e.get("kind") == "eval"]
    measured = len(rows) >= 10
    out_tokens = sum(e["o"] for e in rows) / len(rows) if measured else assumed_output_tokens
    calls = cached = 0
    in_total = 0.0
    for view in views:
        for t in range(trials):
            calls += 1
            if system.cache.get(system.key_for(view, t)) is not None:
                cached += 1
            else:
                in_total += (len(system.system_prompt) + len(system.user_prompt(view))) / CHARS_PER_TOKEN
    uncached = calls - cached
    b = system.budget
    cost = (in_total * b.price_input_per_mtok + uncached * out_tokens * b.price_output_per_mtok) / 1_000_000
    return RunEstimate(calls, cached, int(in_total), int(uncached * out_tokens), round(cost, 4), measured)


__all__ = ["CallOutput", "PromptSystem", "prompt_hash", "RunEstimate", "estimate_calls", "BudgetExceeded"]
