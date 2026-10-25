"""Variety of a set of notes: code-graded, so "more natural and varied" is measured, not felt.

The baseline (round 0, before traits and exemplars) was a top opener share of 100% for copy_forward, 70% for
ehr_template and 40% for ai_scribe: the same first words on most notes.
"""

from __future__ import annotations

import re
from collections import Counter

# A setting's notes may open the same way at most this often. Quick notes open more freely.
MAX_TOP_OPENER_SHARE = {"shorthand": 0.40, "ehr_template": 0.35, "ai_scribe": 0.35, "copy_forward": 0.35}
MIN_DISTINCT_TRAIT_COMBOS = 8  # of a pilot's 20 notes per setting (6 for shorthand, which has fewer traits)


def opener(text: str, words: int = 3) -> str:
    return " ".join(re.findall(r"[a-z']+", text.lower())[:words])


def variety_report(setting: str, texts: list[str], traits: list[dict[str, str]]) -> dict:
    """Top opener share and the number of distinct trait combinations among a setting's accepted notes."""
    n = len(texts)
    openers = Counter(opener(t) for t in texts)
    top, count = openers.most_common(1)[0] if openers else ("", 0)
    combos = len({tuple(sorted(t.items())) for t in traits})
    need = min(n, 6 if setting == "shorthand" else MIN_DISTINCT_TRAIT_COMBOS)
    share = count / n if n else 0.0
    return {
        "notes": n, "top_opener": top, "top_opener_share": round(share, 4),
        "max_top_opener_share": MAX_TOP_OPENER_SHARE[setting],
        "distinct_trait_combos": combos, "min_distinct_trait_combos": need,
        "passed": bool(n) and share <= MAX_TOP_OPENER_SHARE[setting] and combos >= need,
    }
