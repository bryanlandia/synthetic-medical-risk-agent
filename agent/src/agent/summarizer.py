"""The packet's one model step: draft the evidence summary as structured sentences. No tools, no free text from the caller.

The model sees only the criteria table and the evidence list that code built. Whatever it returns is a draft until
``risk_model.summary.verify`` accepts it; the service shows the fixed-template summary otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import Settings

PROMPT = (Path(__file__).with_name("prompts") / "packet.md").read_text()
PACKET_PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()[:12]
MODES = ("normal", "no_citation", "invented_number", "wrong_status", "verdict", "not_json", "fail")


class SummarizerError(RuntimeError):
    """The model could not be reached or failed; the template summary is used and the failure is counted."""


@dataclass
class Draft:
    sentences: Any  # whatever the model returned, parsed; the verifier decides if it is usable
    input_tokens: int = 0
    output_tokens: int = 0


class Summarizer(Protocol):
    model_id: str

    def draft(self, packet: dict[str, Any]) -> Draft: ...


def model_input(packet: dict[str, Any]) -> str:
    """Exactly what the model is shown: the criteria table and the evidence list, and nothing from the caller's message."""
    criteria = [{"id": r["id"], "wording": r["text"], "status": r["status"], "cites": r["cites"]} for r in packet["criteria"]]
    evidence = [{"id": e["id"], "text": e["text"]} for e in packet["evidence"]]
    return json.dumps({"criteria": criteria, "evidence": evidence}, sort_keys=True)


def parse(text: str) -> Any:
    """The JSON array in a model's text (it may be fenced); None when it cannot be read."""
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(body)
    except ValueError:
        return None


class ScriptedSummarizer:
    """A deterministic stand-in: a faithful draft, or one that breaks a verifier rule on purpose."""

    model_id = "scripted"

    def __init__(self, mode: str = "normal"):
        if mode not in MODES:
            raise ValueError(f"unknown scripted summarizer mode {mode!r}; choose from {MODES}")
        self.mode, self.calls = mode, 0

    def draft(self, packet: dict[str, Any]) -> Draft:
        self.calls += 1
        if self.mode == "fail":
            raise SummarizerError("ScriptedFailure")
        if self.mode == "not_json":
            return Draft(sentences=None, input_tokens=300, output_tokens=20)
        evidence = {e["id"]: e for e in packet["evidence"]}
        out = []
        for row in packet["criteria"]:
            facts = "; ".join(evidence[c]["text"] for c in row["cites"])
            text = f"{row['id']} is {row['status']}: {facts}." if row["status"] != "unknown" else f"{row['id']} is unknown: the record does not settle it yet."
            out.append({"criterion": row["id"], "status": row["status"], "text": text, "cites": list(row["cites"])})
        first = out[0]
        if self.mode == "no_citation":
            first["cites"] = []
        elif self.mode == "invented_number":
            first["text"] += " The value was 999 mg/dL."
        elif self.mode == "wrong_status":
            first["status"] = "met" if first["status"] != "met" else "unmet"
        elif self.mode == "verdict":
            first["text"] += " The patient qualifies and the request will be approved."
        return Draft(sentences=out, input_tokens=300, output_tokens=200)


class AnthropicSummarizer:
    """Haiku through the Anthropic API: one call, no tools, a capped output."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_id = settings.model_id
        self.prompt_hash = PACKET_PROMPT_HASH

    def draft(self, packet: dict[str, Any]) -> Draft:
        import anthropic

        client = anthropic.Anthropic(api_key=self.settings.api_key, timeout=self.settings.model_timeout_s, max_retries=1)
        try:
            response = client.messages.create(
                model=self.model_id, max_tokens=self.settings.max_tokens, system=PROMPT,
                messages=[{"role": "user", "content": model_input(packet)}],
                extra_body={"output_config": {"effort": self.settings.effort}})
        except Exception as exc:  # never echo provider details
            raise SummarizerError(type(exc).__name__) from None
        finally:
            client.close()
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        return Draft(sentences=parse(text), input_tokens=int(response.usage.input_tokens), output_tokens=int(response.usage.output_tokens))


def build_summarizer(settings: Settings) -> Summarizer:
    return ScriptedSummarizer() if settings.scripted_model else AnthropicSummarizer(settings)
