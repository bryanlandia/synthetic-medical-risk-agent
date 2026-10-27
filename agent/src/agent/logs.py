"""One structured log line per request. It carries sizes and counts, never the message, the reply, the secret or the key."""

from __future__ import annotations

import json
import logging

LOGGER = logging.getLogger("agent.request")
FIELDS = ("request_id", "status", "tool", "reply_source", "input_tokens", "output_tokens", "cost_usd", "latency_ms",
          "message_chars", "tool_calls", "model_calls", "prompt_hash", "reason")


def log_request(**fields: object) -> None:
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise ValueError(f"not a loggable field: {sorted(unknown)}")  # a new field must be added here on purpose
    LOGGER.info(json.dumps({k: fields[k] for k in FIELDS if k in fields}, sort_keys=True))
