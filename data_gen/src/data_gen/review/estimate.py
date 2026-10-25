"""Dry-run cost estimate for the reviewer. Makes no call and needs no API key."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import GenConfig
from ..llm.gateway import DiskCache, cache_key
from .prompt import REVIEWER_SYSTEM, review_prompt

CHARS_PER_TOKEN = 3.0
ASSUMED_OUTPUT_TOKENS = {"low": 250, "medium": 700, "high": 1500}  # JSON answer plus thinking
RETRY_RATE = 0.10
MIN_MEASURED = 10


@dataclass
class ReviewEstimate:
    notes: int
    calls: int  # first-attempt calls not already cached
    cached: int
    expected_retry_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    measured: bool

    @property
    def uncached_calls(self) -> int:
        return self.calls + self.expected_retry_calls


def estimate_review(cfg: GenConfig, sheet: dict, cache: DiskCache | None = None) -> ReviewEstimate:
    lc = cfg.llm
    rows = [e for e in (cache.entries.values() if cache else []) if e.get("kind") == "reviewer"]
    measured = len(rows) >= MIN_MEASURED
    avg_in = sum(e["i"] for e in rows) / len(rows) if measured else None
    avg_out = sum(e["o"] for e in rows) / len(rows) if measured else float(ASSUMED_OUTPUT_TOKENS[lc.reviewer_effort])
    calls = cached = 0
    in_tok = 0.0
    for note in sheet["notes"]:
        prompt = review_prompt(note["text"])
        key = cache_key(lc.reviewer_prompt_version, REVIEWER_SYSTEM, prompt, lc.reviewer_model_id,
                        lc.reviewer_max_tokens, 0)
        if cache and cache.get(key) is not None:
            cached += 1
            continue
        calls += 1
        in_tok += avg_in if avg_in is not None else (len(REVIEWER_SYSTEM) + len(prompt)) / CHARS_PER_TOKEN
    retries = round(calls * RETRY_RATE)
    total_calls = calls + retries
    per_call_in = in_tok / calls if calls else 0.0
    in_total = int(in_tok + retries * per_call_in)
    out_total = int(total_calls * avg_out)
    cost = (in_total * lc.reviewer_price_input_per_mtok + out_total * lc.reviewer_price_output_per_mtok) / 1_000_000
    return ReviewEstimate(len(sheet["notes"]), calls, cached, retries, in_total, out_total, round(cost, 4), measured)


TURNS_PER_NOTE = 2.3  # one turn of tool calls to rate, one to move on, and the odd correction
BROWSER_INPUT_PER_TURN = 1500  # persona, tool definitions, the note and earlier results of this note
BROWSER_OUTPUT_PER_TURN = {"low": 250, "medium": 500, "high": 1000}


def estimate_browser(cfg: GenConfig, n_notes: int) -> ReviewEstimate:
    """Browser mode is not cached (every turn depends on the page), so all turns are paid."""
    lc = cfg.llm
    turns = round(n_notes * TURNS_PER_NOTE)
    in_total = turns * BROWSER_INPUT_PER_TURN
    out_total = turns * BROWSER_OUTPUT_PER_TURN[lc.reviewer_effort]
    cost = (in_total * lc.reviewer_price_input_per_mtok + out_total * lc.reviewer_price_output_per_mtok) / 1_000_000
    return ReviewEstimate(n_notes, turns, 0, 0, in_total, out_total, round(cost, 4), False)
