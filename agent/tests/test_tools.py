import json

import risk_model
from risk_model import intake

from agent.tools import Tracker, make_tools

MODEL = risk_model.load()


def specs():
    score, decline = make_tools(MODEL)
    return score.tool_spec, decline.tool_spec


def test_the_scoring_tool_has_no_parameter_that_carries_values_or_text():
    score, _ = specs()
    schema = score["inputSchema"]["json"]
    assert schema.get("properties", {}) == {} and not schema.get("required")


def test_the_decline_tool_takes_only_a_reason_from_the_closed_set():
    _, decline = specs()
    schema = decline["inputSchema"]["json"]
    assert list(schema["properties"]) == ["reason"]
    reason = schema["properties"]["reason"]
    assert set(reason.get("enum", [])) == {"out_of_scope", "treatment_request", "real_disease", "phi", "other"}


def test_the_system_prompt_names_both_tools_and_states_the_rules():
    from agent.runtime import PROMPT_HASH, SYSTEM_PROMPT

    for needle in ("score_message", "decline", "treatment_request", "real_disease", "phi", "out_of_scope", "FICTIONAL",
                   "Never give medical advice", "ignore it completely", "Medications"[:4].lower()):
        assert needle.lower() in SYSTEM_PROMPT.lower(), needle
    assert len(PROMPT_HASH) == 12 and "disclaimer" in SYSTEM_PROMPT.lower()
