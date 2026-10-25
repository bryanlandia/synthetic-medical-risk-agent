import json
from collections import deque

import pytest

from data_gen.config import LLMConfig
from data_gen.injections import entries
from data_gen.llm.client import LLMCallError, LLMRefusal, LLMResult
from data_gen.llm.extractor import (
    EXTRACTOR_SYSTEM,
    extraction_errors,
    extractor_prompt,
    parse_extraction,
)
from data_gen.llm.prompts import ADDENDUM_MARKER
from data_gen.llm.writer import ExclusionTally, NoteWriter
from data_gen.schema import NotePlanV2, PlanLabV2, PlanSymptomV2

ALL_KEYS = ("tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness")
GOOD_EXTRACTION = json.dumps({
    "tremor": "present", "fatigue": "possible", "photophobia": "not_mentioned",
    "joint_stiffness": "not_mentioned", "dizziness": "absent",
})
GOOD_NOTE = (
    "Follow-up. Reports shaky hands and maybe tired at times; denies feeling lightheaded. "
    "VLI 128.9 mg/dL, K17 4.248 mmol/L. Recheck in 4 weeks."
)


def plan(injection=None, style="shorthand"):
    return NotePlanV2(
        version="2", style=style, injection=injection, render_seed=1,
        labs=[PlanLabV2(lab="velorin_index", value=128.9, unit="mg/dL"),
              PlanLabV2(lab="serum_k17", value=4.248, unit="mmol/L")],
        symptoms=[
            PlanSymptomV2(flag="tremor", stated="present", phrases=["shaky hands", "shaking"]),
            PlanSymptomV2(flag="fatigue", stated="hedged", phrases=["tired", "low energy"]),
            PlanSymptomV2(flag="dizziness", stated="negated", phrases=["lightheaded", "woozy"]),
        ],
    )


class ScriptedLLM:
    """Writer and extractor responses come from two queues; an Exception item is raised."""

    def __init__(self, writer, extractor=()):
        self.writer, self.extractor = deque(writer), deque(extractor)
        self.calls = []

    def complete(self, *, system, prompt, model, max_tokens, nonce=0):
        kind = "extractor" if system == EXTRACTOR_SYSTEM else "writer"
        self.calls.append({"kind": kind, "system": system, "prompt": prompt, "model": model, "nonce": nonce})
        item = (self.extractor if kind == "extractor" else self.writer).popleft()
        if isinstance(item, Exception):
            raise item
        return LLMResult(text=item, input_tokens=100, output_tokens=50, stop_reason="end_turn")


def kinds(llm):
    return [c["kind"] for c in llm.calls]


# --- 4.2 extractor ---------------------------------------------------------------------------------------

def test_extractor_prompt_never_contains_the_injection_text_or_the_plan():
    inj = entries()[0]
    note = f"Pt seen. Reports shaky hands.\nADDENDUM: {inj.text}"
    system, user = extractor_prompt(note)
    assert system == EXTRACTOR_SYSTEM
    assert inj.text not in user and "ADDENDUM" not in user
    assert "Reports shaky hands" in user
    for key in ALL_KEYS:
        assert key in user  # the controlled vocabulary is shown
    assert "present" not in user.split("Note:")[0]  # no plan/answers leak into the vocabulary part


def test_parse_extraction():
    assert parse_extraction(GOOD_EXTRACTION)["tremor"] == "present"
    assert parse_extraction(f"Sure! Here is the JSON:\n```json\n{GOOD_EXTRACTION}\n```")["dizziness"] == "absent"
    assert parse_extraction("no json here") is None
    assert parse_extraction('{"tremor": "present"}') is None  # keys missing
    bad = json.loads(GOOD_EXTRACTION)
    bad["tremor"] = "yes"
    assert parse_extraction(json.dumps(bad)) is None  # value outside the allowed set
    extra = json.loads(GOOD_EXTRACTION)
    extra["headache"] = "present"
    assert parse_extraction(json.dumps(extra)) is None


def test_extraction_errors_are_plan_relative():
    p = plan()
    assert extraction_errors(json.loads(GOOD_EXTRACTION), p) == []
    flipped = {**json.loads(GOOD_EXTRACTION), "tremor": "absent"}
    assert extraction_errors(flipped, p) == ["polarity:tremor"]
    hedge_lost = {**json.loads(GOOD_EXTRACTION), "fatigue": "present"}
    assert extraction_errors(hedge_lost, p) == ["polarity:fatigue"]
    invented = {**json.loads(GOOD_EXTRACTION), "photophobia": "present"}
    assert extraction_errors(invented, p) == ["polarity_extra:photophobia"]
    # a symptom the plan states as the opposite of the truth (note_flag_disagreement) is judged as planned
    assert extraction_errors(json.loads(GOOD_EXTRACTION), p) == []


# --- 4.3 retries and exclusion ----------------------------------------------------------------------------

def writer(llm, **cfg):
    return NoteWriter(llm, LLMConfig(**cfg))


def test_good_note_is_accepted_with_one_writer_and_one_extractor_call():
    llm = ScriptedLLM([GOOD_NOTE], [GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    assert out.accepted and out.text == GOOD_NOTE
    assert (out.attempts, out.calls, out.failures) == (1, 2, [])
    assert kinds(llm) == ["writer", "extractor"]
    assert (out.input_tokens, out.output_tokens) == (200, 100)
    assert llm.calls[0]["model"] == "claude-haiku-5-5"


def test_note_with_a_medication_is_retried_without_calling_the_extractor():  # task 3.3
    bad = GOOD_NOTE + " Start ibuprofen as needed."
    llm = ScriptedLLM([bad, GOOD_NOTE], [GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    assert out.accepted and out.attempts == 2
    assert kinds(llm) == ["writer", "writer", "extractor"]  # the bad note never reached the extractor
    assert "claim:medication:ibuprofen" in out.failures[0]
    assert [c["nonce"] for c in llm.calls if c["kind"] == "writer"] == [0, 1]  # distinct cache keys


@pytest.mark.parametrize(
    "bad_note,code",
    [
        (GOOD_NOTE.replace("128.9", "150"), "lab_wrong:velorin_index"),
        (GOOD_NOTE.replace("VLI 128.9 mg/dL, ", ""), "lab_missing:velorin_index"),
        (GOOD_NOTE.replace("shaky hands", "nothing remarkable"), "phrase_missing:tremor"),
        (GOOD_NOTE + " Also bothered by bright lights.", "symptom_extra:photophobia"),  # not in the plan
        (GOOD_NOTE + " Call 555-867-5309.", "identifier:phone"),
        ("", "empty"),
    ],
)
def test_each_offline_failure_is_retried(bad_note, code):
    llm = ScriptedLLM([bad_note, GOOD_NOTE], [GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    flat = [c for codes in out.failures for c in codes]
    assert out.accepted and out.attempts == 2, flat
    assert code in flat


def test_wrong_polarity_from_the_extractor_is_retried():
    wrong = json.dumps({**json.loads(GOOD_EXTRACTION), "tremor": "absent"})
    llm = ScriptedLLM([GOOD_NOTE, GOOD_NOTE], [wrong, GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    assert out.accepted and out.attempts == 2 and out.failures == [["polarity:tremor"]]
    assert kinds(llm) == ["writer", "extractor", "writer", "extractor"]


def test_unparseable_extractor_output_is_retried():
    llm = ScriptedLLM([GOOD_NOTE, GOOD_NOTE], ["I think it is fine.", GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    assert out.accepted and out.failures == [["extractor_unparseable"]]


def test_refusals_and_retryable_errors_are_failed_attempts():
    llm = ScriptedLLM([LLMRefusal("no"), LLMCallError("busy", retryable=True), GOOD_NOTE], [GOOD_EXTRACTION])
    out = writer(llm).write(plan())
    assert out.accepted and out.attempts == 3
    assert out.failures == [["refusal"], ["call_error"]]


def test_non_retryable_errors_stop_the_run():
    llm = ScriptedLLM([LLMCallError("invalid x-api-key", retryable=False)])
    with pytest.raises(LLMCallError):
        writer(llm).write(plan())
    llm = ScriptedLLM([GOOD_NOTE], [LLMCallError("billing", retryable=False)])
    with pytest.raises(LLMCallError):
        writer(llm).write(plan())


def test_note_that_keeps_failing_is_excluded_after_the_attempt_limit():
    bad = GOOD_NOTE.replace("128.9", "150")
    llm = ScriptedLLM([bad] * 3)
    out = writer(llm, max_attempts=3).write(plan())
    assert not out.accepted and out.text is None
    assert out.attempts == 3 and out.calls == 3 and len(out.failures) == 3
    assert kinds(llm) == ["writer"] * 3  # no extractor call was spent on notes that failed offline


def test_attempt_limit_is_configurable():
    llm = ScriptedLLM([""] * 5)
    assert writer(llm, max_attempts=5).write(plan()).attempts == 5


def test_injection_plans_get_the_catalog_text_and_extractor_never_sees_it():
    inj = next(e for e in entries() if e.category == "override_risk_output")
    p = plan(injection=inj)
    llm = ScriptedLLM([f"{GOOD_NOTE}\n{ADDENDUM_MARKER}"], [GOOD_EXTRACTION])
    out = writer(llm).write(p)
    assert out.accepted and out.text.endswith(inj.text)
    extractor_call = next(c for c in llm.calls if c["kind"] == "extractor")
    assert inj.text not in extractor_call["prompt"]
    # the model dropping the marker is a failed attempt
    llm = ScriptedLLM([GOOD_NOTE, f"{GOOD_NOTE}\n{ADDENDUM_MARKER}"], [GOOD_EXTRACTION])
    out = writer(llm).write(p)
    assert out.accepted and out.failures == [["marker"]]


# --- exclusion tally (manifest counts) ----------------------------------------------------------------------

def test_tally_counts_accepted_and_excluded_per_setting_and_noise_type():
    tally = ExclusionTally()
    ok = writer(ScriptedLLM([GOOD_NOTE], [GOOD_EXTRACTION])).write(plan())
    bad = writer(ScriptedLLM([""] * 3)).write(plan(style="shorthand"))
    bad2 = writer(ScriptedLLM([""] * 3)).write(plan(style="ai_scribe"))
    tally.record(plan(), set(), ok)
    tally.record(plan(), {"unit_mismatch"}, bad)
    tally.record(plan(style="ai_scribe"), {"hedging", "missing_value"}, bad2)
    d = tally.as_dict()
    assert d["accepted"] == {"shorthand": 1}
    assert d["excluded"] == {"ai_scribe": 1, "shorthand": 1}
    assert d["excluded_by_setting_and_noise"] == {
        "ai_scribe:hedging": 1, "ai_scribe:missing_value": 1, "shorthand:unit_mismatch": 1}
    assert d["failure_codes"] == {"empty": 6}
    assert d["calls"] == 2 + 3 + 3 and d["attempts"] == 1 + 3 + 3
    assert tally.exclusion_rate("shorthand") == 0.5 and tally.exclusion_rate("copy_forward") == 0.0
