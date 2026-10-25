"""Dry-run cost estimate. Makes no LLM call and needs no API key.

It counts the calls a run would make (one writer call and one extractor call per note, plus expected
retries), subtracts what is already cached, and prices the rest. Token counts are assumptions until the
cache holds real measurements: once there are enough cached calls of a kind, their average is used, so an
estimate made after the pilot is calibrated by the pilot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config import GenConfig
from .checks import offline_errors
from .extractor import EXTRACTOR_MAX_TOKENS, extractor_prompt
from .gateway import DiskCache, cache_key
from .prompts import MarkerError, build_prompt, finalize_note
from .run import PlanItem

CHARS_PER_TOKEN = 3.0  # conservative for the current tokenizer (it counts about 30% more than older ones)
THINKING_ALLOWANCE = {"writer": 150, "extractor": 100}  # output tokens billed for brief 'low' effort thinking
NOTE_WORDS = {"shorthand": 45, "ehr_template": 130, "ai_scribe": 130, "copy_forward": 120}
TOKENS_PER_WORD = 1.7
EXTRACTOR_OUTPUT = 65
MIN_MEASURED = 10  # use measured averages once the cache has this many calls of a kind
DEFAULT_RETRY_RATE = 0.25  # expected extra attempts per note


@dataclass
class Estimate:
    notes: int
    per_setting: dict[str, int]
    first_attempt_calls: int  # writer + extractor calls that are not cached
    cached_calls: int
    expected_retry_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    assumptions: dict = field(default_factory=dict)

    @property
    def uncached_calls(self) -> int:
        return self.first_attempt_calls + self.expected_retry_calls

    def as_dict(self) -> dict:
        return {**self.__dict__, "uncached_calls": self.uncached_calls}


def _tokens(chars: int) -> float:
    return chars / CHARS_PER_TOKEN


def estimate(
    cfg: GenConfig, items: list[PlanItem], cache: DiskCache | None = None,
    *, retry_rate: float = DEFAULT_RETRY_RATE,
) -> Estimate:
    lc = cfg.llm
    measured = {k: (cache.average_tokens(k) if cache else None) for k in ("writer", "extractor")}
    counts = {k: sum(1 for e in cache.entries.values() if e.get("kind") == k) if cache else 0
              for k in ("writer", "extractor")}
    use_measured = {k: measured[k] is not None and counts[k] >= MIN_MEASURED for k in measured}

    first = cached = 0
    in_tok = out_tok = 0.0
    per_setting: dict[str, int] = {}
    for item in items:
        plan = item.planned.plan
        per_setting[plan.style] = per_setting.get(plan.style, 0) + 1
        prompt = build_prompt(plan)
        w_key = cache_key(lc.prompt_version, prompt.system, prompt.user, lc.model_id, lc.max_tokens, 0)
        w_hit = cache.get(w_key) if cache else None
        x_hit = False
        if w_hit is not None:
            cached += 1
            x_hit = _extractor_cached(cfg, plan, w_hit.text, cache)
            cached += x_hit
        # price what is not cached
        if w_hit is None:
            first += 1
            in_tok, out_tok = _add(in_tok, out_tok, "writer", use_measured, measured,
                                   _tokens(len(prompt.system) + len(prompt.user)),
                                   NOTE_WORDS[plan.style] * TOKENS_PER_WORD + THINKING_ALLOWANCE["writer"])
        if not x_hit:
            first += 1
            sys_x, user_x = extractor_prompt("x" * (NOTE_WORDS[plan.style] * 6))
            in_tok, out_tok = _add(in_tok, out_tok, "extractor", use_measured, measured,
                                   _tokens(len(sys_x) + len(user_x)),
                                   EXTRACTOR_OUTPUT + THINKING_ALLOWANCE["extractor"])
    retry_calls = math.ceil(first * retry_rate)
    if first:
        in_tok *= 1 + retry_rate
        out_tok *= 1 + retry_rate
    cost = (in_tok * lc.price_input_per_mtok + out_tok * lc.price_output_per_mtok) / 1_000_000
    return Estimate(
        notes=len(items), per_setting=dict(sorted(per_setting.items())), first_attempt_calls=first,
        cached_calls=cached, expected_retry_calls=retry_calls, input_tokens=round(in_tok),
        output_tokens=round(out_tok), cost_usd=round(cost, 4),
        assumptions={
            "model_id": lc.model_id, "retry_rate": retry_rate, "chars_per_token": CHARS_PER_TOKEN,
            "measured_writer_tokens_used": use_measured["writer"],
            "measured_extractor_tokens_used": use_measured["extractor"],
            "price_per_mtok_in_out": [lc.price_input_per_mtok, lc.price_output_per_mtok],
            "caps": {"max_calls": lc.max_calls, "max_spend_usd": lc.max_spend_usd},
        },
    )


def _add(in_tok, out_tok, kind, use_measured, measured, est_in, est_out):
    if use_measured[kind]:
        est_in, est_out = measured[kind]
    return in_tok + est_in, out_tok + est_out


def _extractor_cached(cfg: GenConfig, plan, writer_text: str, cache: DiskCache) -> bool:
    """Is the extractor call for this cached writer output cached too? (Assumes the first attempt passed.)"""
    try:
        note = finalize_note(writer_text, plan)
    except MarkerError:
        return False
    if offline_errors(note, plan):
        return False  # a retry will happen; its calls are counted as expected retries
    system, user = extractor_prompt(note)
    key = cache_key(cfg.llm.prompt_version, system, user, cfg.llm.model_id, EXTRACTOR_MAX_TOKENS, 0)
    return cache.get(key) is not None


def exceeds_caps(cfg: GenConfig, est: Estimate) -> list[str]:
    warnings = []
    if est.uncached_calls > cfg.llm.max_calls:
        warnings.append(f"expected calls {est.uncached_calls} exceed llm.max_calls {cfg.llm.max_calls}")
    if est.cost_usd > cfg.llm.max_spend_usd:
        warnings.append(f"estimated cost ${est.cost_usd:.2f} exceeds llm.max_spend_usd ${cfg.llm.max_spend_usd:.2f}")
    return warnings
