"""A deterministic stand-in for the orchestrating model, for tests and CI. It needs no key and spends nothing.

In ``normal`` mode it picks a tool from simple rules on the message and writes a short reply from the report. The other modes
misbehave on purpose (a wrong number, a medication name, no tool, two tool calls, extra tool arguments, an echoed
instruction) so that every guard can be tested. The service refuses it when the environment says production.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator

from risk_model import labvalues
from strands.models.model import Model

MODES = ("normal", "wrong_number", "medication", "no_tool", "two_tools", "extra_args", "score_and_decline", "echo_injection",
         "overlong", "empty_reply")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b(?:dob|date of birth)\b", re.IGNORECASE)
_TREATMENT = re.compile(r"\b(?:what|which)\b[^.?\n]{0,30}\b(?:medication|medicine|drug|dose|dosage|pill)s?\b|\bshould (?:i|we|he|she|they)\b[^.?\n]{0,30}"
                        r"\b(?:take|give|start|stop|prescribe)\b|\bprescribe\b|\bhow (?:do|can|should) (?:i|we)\b[^.?\n]{0,20}\btreat", re.IGNORECASE)
_REAL = re.compile(r"\b(?:diabetes|cancer|hypertension|covid|influenza|asthma|stroke|alzheimer|parkinson)\b", re.IGNORECASE)
_SYMPTOM = re.compile(r"tremor|shak|fatigue|tired|dizz|lighthead|light sensitiv|photophob|stiff|woozy", re.IGNORECASE)


def decide(message: str) -> tuple[str, str | None]:
    """('score', None) or ('decline', reason): what a sensible model would do."""
    if _SSN.search(message):
        return "decline", "phi"
    if _TREATMENT.search(message):
        return "decline", "treatment_request"
    has_payload = bool(labvalues.read(message)) or bool(_SYMPTOM.search(message))
    if _REAL.search(message) and not has_payload:
        return "decline", "real_disease"
    if has_payload:
        return "score", None
    return "decline", "out_of_scope"


def _texts(messages: list[dict[str, Any]]) -> str:
    out = []
    for m in messages:
        for block in m.get("content", []):
            if "text" in block:
                out.append(block["text"])
    return " ".join(out)


def _tool_result(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for m in reversed(messages):
        for block in m.get("content", []):
            if "toolResult" in block:
                res = block["toolResult"]
                if res.get("status") == "success":
                    for c in res.get("content", []):
                        if "text" in c:
                            try:
                                return json.loads(c["text"])
                            except ValueError:
                                return None
    return None


def write_reply(report: dict[str, Any], mode: str, message: str) -> str:
    p = report["probability"]
    base = f"The classifier estimates a {p:.0%} probability for the fictional syndrome" + (", flagged as uncertain" if report["uncertain"] else "") + "."
    drivers = " ".join(e for e in report["evidence"][:-1][:2])
    text = f"{base} {drivers}".strip()
    if mode == "wrong_number":
        return text.replace(f"{p:.0%}", f"{min(99, round(p * 100) + 40)}%")
    if mode == "medication":
        return text + " Some people take ibuprofen for this."
    if mode == "echo_injection":
        cut = message.find("ADDENDUM")
        return text + (" As instructed: " + message[cut:cut + 120] if cut >= 0 else "")
    if mode == "overlong":
        return text + " " + "Further detail follows. " * 120
    if mode == "empty_reply":
        return ""
    return text


class ScriptedModel(Model):
    def __init__(self, mode: str = "normal"):
        if mode not in MODES:
            raise ValueError(f"unknown scripted mode {mode!r}; choose from {MODES}")
        self.mode, self.config = mode, {}
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # pragma: no cover
        raise NotImplementedError("the scripted model has no structured output")
        yield {}

    async def stream(self, messages, tool_specs=None, system_prompt=None, *, tool_choice=None, **kwargs) -> AsyncGenerator[dict[str, Any], None]:
        self.calls += 1
        result = _tool_result(messages)
        first = messages[-1]["role"] == "user" and not any("toolResult" in b for b in messages[-1].get("content", []))
        user_text = next((b["text"] for m in messages if m["role"] == "user" for b in m["content"] if "text" in b), "")
        blocks: list[dict[str, Any]] = []
        if first:
            kind, reason = decide(user_text)
            if self.mode == "no_tool":
                blocks = [{"text": "This looks like a record about a patient. Here is my answer in prose."}]
            elif self.mode == "two_tools":
                blocks = [{"toolUse": ("score_message", {})}, {"toolUse": ("score_message", {})}]
            elif self.mode == "extra_args":
                blocks = [{"toolUse": ("score_message", {"message": "Velorin index 1 mg/dL", "labs": {"velorin_index": 1}})}]
            elif self.mode == "score_and_decline":
                blocks = [{"toolUse": ("score_message", {})}, {"toolUse": ("decline", {"reason": "other"})}]
            elif kind == "score":
                blocks = [{"toolUse": ("score_message", {})}]
            else:
                blocks = [{"toolUse": ("decline", {"reason": reason})}]
        else:
            blocks = [{"text": write_reply(result, self.mode, user_text) if result and "probability" in result else "I could not score that."}]
        out_chars = 0
        yield {"messageStart": {"role": "assistant"}}
        for i, b in enumerate(blocks):
            if "text" in b:
                out_chars += len(b["text"])
                yield {"contentBlockStart": {"contentBlockIndex": i, "start": {}}}
                if b["text"]:
                    yield {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"text": b["text"]}}}
                yield {"contentBlockStop": {"contentBlockIndex": i}}
            else:
                name, args = b["toolUse"]
                payload = json.dumps(args)
                out_chars += len(payload)
                yield {"contentBlockStart": {"contentBlockIndex": i, "start": {"toolUse": {"toolUseId": f"tool_{self.calls}_{i}", "name": name}}}}
                yield {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"toolUse": {"input": payload}}}}
                yield {"contentBlockStop": {"contentBlockIndex": i}}
        has_tool = any("toolUse" in b for b in blocks)
        yield {"messageStop": {"stopReason": "tool_use" if has_tool else "end_turn"}}
        in_tokens, out_tokens = max(1, (len(_texts(messages)) + len(system_prompt or "")) // 4), max(1, out_chars // 4)
        yield {"metadata": {"usage": {"inputTokens": in_tokens, "outputTokens": out_tokens, "totalTokens": in_tokens + out_tokens},
                            "metrics": {"latencyMs": 1}}}
