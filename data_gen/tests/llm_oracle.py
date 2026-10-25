"""A fake LLM for run-level tests: it writes a faithful note for any plan, and extracts it faithfully.

It is given the plans up front and looks them up by prompt text, so it needs no knowledge of the prompts
beyond their format. ``fail_setting`` makes one setting always produce an unusable note.
"""

from __future__ import annotations

import json

from data_gen.llm.client import LLMResult
from data_gen.llm.extractor import EXTRACTOR_SYSTEM
from data_gen.llm.prompts import ADDENDUM_MARKER, build_prompt
from data_gen.labs import LAB_BY_KEY, SYMPTOM_BY_KEY
from data_gen.schema import NotePlanV2

_STATUS = {"present": "present", "hedged": "possible", "negated": "absent"}


_OPENER = {"shorthand": "Brief visit.", "ehr_template": "Clinic follow-up.",
           "ai_scribe": "Summary of today.", "copy_forward": "Progress note."}


def fake_note(plan: NotePlanV2) -> str:
    sentences = []
    for s in plan.symptoms:
        phrase = s.phrases[0]
        sentences.append({"present": f"Reports {phrase}", "hedged": f"Possibly {phrase}",
                          "negated": f"Denies {phrase}"}[s.stated])
    labs = []
    for lab in plan.labs:
        text = f"{LAB_BY_KEY[lab.lab].abbr} {lab.value:g} {lab.unit}"
        if lab.flag:
            text += f" ({lab.flag})"
        if lab.ref_range:
            text += f", reference {lab.ref_range[0]:g}-{lab.ref_range[1]:g} {lab.unit}"
        labs.append(text)
    parts = [_OPENER[plan.style], "; ".join(sentences) + ("." if sentences else ""), "; ".join(labs) + ("." if labs else ""),
             "Recheck in 4 weeks."]
    return " ".join(p for p in parts if p.strip("."))


def expected_extraction(plan: NotePlanV2) -> dict[str, str]:
    planned = {s.flag: _STATUS[s.stated] for s in plan.symptoms}
    return {key: planned.get(key, "not_mentioned") for key in SYMPTOM_BY_KEY}


class OracleLLM:
    def __init__(self, items, fail_setting: str | None = None, fail_every: int | None = None):
        self.by_prompt = {build_prompt(i.planned.plan).user: i.planned.plan for i in items}
        # Notes are a pure function of the plan, so a resumed run (writer outputs served from the cache)
        # can still map a note back to its plan.
        self.by_body: dict[str, NotePlanV2] = {fake_note(i.planned.plan).strip(): i.planned.plan for i in items}
        # fail_setting: a setting name, or "*" for all. fail_every: only every Nth distinct prompt (default all).
        self.fail_setting, self.fail_every = fail_setting, fail_every
        # The failing notes are chosen by position in the plan list, not by arrival order, so which notes fail
        # does not depend on how many workers happen to call at once.
        self.ordinal: dict[str, int] = {}
        for i in items:
            self.ordinal.setdefault(build_prompt(i.planned.plan).user, len(self.ordinal))
        self.calls: list[str] = []

    def complete(self, *, system, prompt, model, max_tokens, nonce=0):
        if system == EXTRACTOR_SYSTEM:
            self.calls.append("extractor")
            body = prompt.split('Note:\n"""\n', 1)[1].rsplit('\n"""', 1)[0].strip()
            return LLMResult(json.dumps(expected_extraction(self.by_body[body])), 400, 60, "end_turn")
        self.calls.append("writer")
        plan = self.by_prompt[prompt]
        if self.fail_setting in (plan.style, "*"):
            n = self.ordinal[prompt]
            if self.fail_every is None or n % self.fail_every == 0:
                return LLMResult("no usable content here", 600, 20, "end_turn")
        body = fake_note(plan)
        return LLMResult(body + (f"\n{ADDENDUM_MARKER}" if plan.injection else ""), 600, 120, "end_turn")
