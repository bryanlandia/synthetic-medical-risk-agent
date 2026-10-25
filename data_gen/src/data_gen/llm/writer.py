"""Write one note from a plan: generate, validate, retry a bounded number of times, else exclude."""

from __future__ import annotations

import logging
import random
import time
from collections import Counter
from dataclasses import dataclass, field

from ..config import LLMConfig
from ..schema import NotePlanV2
from .checks import offline_errors
from .client import LLMCallError, LLMClient, LLMRefusal
from .extractor import EXTRACTOR_MAX_TOKENS, extraction_errors, extractor_prompt, parse_extraction
from .prompts import MarkerError, build_prompt, finalize_note

log = logging.getLogger("data_gen.llm")

RATE_LIMIT_RETRIES = 6  # waits of about 1, 2, 4, 8, 16, 32 seconds (with jitter) before giving up on a call
MAX_BACKOFF_SECONDS = 32.0


class TooManyExclusions(RuntimeError):
    """Most notes are failing validation, which points at a prompt, limit or checker problem, not bad luck.
    The run stops instead of spending money on retries that will not help."""


@dataclass
class WriteOutcome:
    text: str | None  # None = excluded
    attempts: int = 0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failures: list[list[str]] = field(default_factory=list)  # failure codes of each failed attempt
    extraction: dict[str, str] | None = None  # the extractor's reading of the accepted note

    @property
    def accepted(self) -> bool:
        return self.text is not None


class NoteWriter:
    def __init__(self, client: LLMClient, cfg: LLMConfig, sleep=time.sleep):
        self.client = client
        self.cfg = cfg
        self.sleep = sleep  # injectable so tests need not wait

    def write(self, plan: NotePlanV2) -> WriteOutcome:
        prompt = build_prompt(plan)
        out = WriteOutcome(text=None)
        for attempt in range(self.cfg.max_attempts):
            out.attempts += 1
            codes = self._attempt(plan, prompt.system, prompt.user, attempt, out)
            if isinstance(codes, str):
                out.text = codes
                return out
            out.failures.append(codes)
            log.info("%s note, attempt %d/%d failed: %s", plan.style, attempt + 1, self.cfg.max_attempts,
                     ", ".join(codes))
        log.warning("%s note excluded after %d attempts", plan.style, out.attempts)
        return out

    def _complete(self, **kwargs):
        """One call, retried with exponential backoff while the API says it is rate limited or overloaded.
        These waits do not use up the note's attempts: being throttled says nothing about the note."""
        wait = 1.0
        for retry in range(RATE_LIMIT_RETRIES + 1):
            try:
                return self.client.complete(model=self.cfg.model_id, **kwargs)
            except LLMCallError as exc:
                if not exc.rate_limited or retry == RATE_LIMIT_RETRIES:
                    raise
                pause = min(wait, MAX_BACKOFF_SECONDS) * (0.5 + random.random() / 2)
                log.warning("rate limited; waiting %.1fs before retry %d/%d", pause, retry + 1, RATE_LIMIT_RETRIES)
                self.sleep(pause)
                wait *= 2
        raise AssertionError("unreachable")  # pragma: no cover

    def _call(self, out: WriteOutcome, **kwargs):
        result = self._complete(**kwargs)
        out.calls += 1
        out.input_tokens += result.input_tokens
        out.output_tokens += result.output_tokens
        return result

    def _attempt(self, plan: NotePlanV2, system: str, user: str, attempt: int, out: WriteOutcome):
        """Return the accepted text, or a list of failure codes."""
        try:
            result = self._call(out, system=system, prompt=user, max_tokens=self.cfg.max_tokens, nonce=attempt)
        except LLMRefusal:
            return ["refusal"]
        except LLMCallError as exc:
            if not exc.retryable:
                raise  # authentication, billing or request errors will not fix themselves: stop the run
            return ["call_error"]
        if result.stop_reason == "max_tokens":
            return ["truncated"]  # a cut-off note must never be judged as if it were complete
        try:
            text = finalize_note(result.text, plan)
        except MarkerError:
            return ["marker"]
        codes = offline_errors(text, plan)
        if codes:
            return codes
        system_x, user_x = extractor_prompt(text)
        try:
            extraction = self._call(out, system=system_x, prompt=user_x, max_tokens=EXTRACTOR_MAX_TOKENS, nonce=attempt)
        except LLMRefusal:
            return ["extractor_refusal"]
        except LLMCallError as exc:
            if not exc.retryable:
                raise
            return ["extractor_call_error"]
        if extraction.stop_reason == "max_tokens":
            return ["extractor_truncated"]
        extracted = parse_extraction(extraction.text)
        if extracted is None:
            return ["extractor_unparseable"]
        codes = extraction_errors(extracted, plan)
        if not codes:
            out.extraction = extracted
        return codes or text


@dataclass
class ExclusionTally:
    """Counts what was accepted and excluded, per setting and noise type, for the manifest."""

    accepted: Counter = field(default_factory=Counter)
    excluded: Counter = field(default_factory=Counter)
    excluded_by_noise: Counter = field(default_factory=Counter)
    failure_codes: Counter = field(default_factory=Counter)
    attempts: int = 0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, plan: NotePlanV2, noise_types: set[str], outcome: WriteOutcome) -> None:
        self.attempts += outcome.attempts
        self.calls += outcome.calls
        self.input_tokens += outcome.input_tokens
        self.output_tokens += outcome.output_tokens
        for codes in outcome.failures:
            self.failure_codes.update(c.split(":")[0] for c in codes)
        if outcome.accepted:
            self.accepted[plan.style] += 1
        else:
            self.excluded[plan.style] += 1
            for n in noise_types or {"none"}:
                self.excluded_by_noise[f"{plan.style}:{n}"] += 1

    def attempted(self, setting: str) -> int:
        return self.accepted[setting] + self.excluded[setting]

    def exclusion_rate(self, setting: str) -> float:
        total = self.attempted(setting)
        return self.excluded[setting] / total if total else 0.0

    def total_exclusion_rate(self) -> float:
        total = sum(self.accepted.values()) + sum(self.excluded.values())
        return sum(self.excluded.values()) / total if total else 0.0

    def top_failures(self, n: int = 3) -> str:
        return ", ".join(f"{code} x{count}" for code, count in self.failure_codes.most_common(n)) or "none"

    def as_dict(self) -> dict:
        return {
            "accepted": dict(sorted(self.accepted.items())),
            "excluded": dict(sorted(self.excluded.items())),
            "excluded_by_setting_and_noise": dict(sorted(self.excluded_by_noise.items())),
            "failure_codes": dict(sorted(self.failure_codes.items())),
            "attempts": self.attempts,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
