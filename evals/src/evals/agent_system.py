"""The ``agent`` system: a record becomes a chat message, the running service answers, and the returned report is graded.

A declined response, an HTTP error or an unreadable body is returned as text that does not parse, so the graders count it as
an invalid report. Every call is also kept as a small record (tool calls, decline reason, reply, cost) for the tool-use and
scope graders. Within a run, the same message and trial index are sent once, so a record that appears in several suites
costs one call; a repeated trial is a different key and is a real second call.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx

from .messages import render_message
from .prompt_system import CallOutput

SECRET_HEADER = "x-shared-secret"
FAILURE_PREFIX = "[agent"
RETRYABLE = (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError, httpx.ConnectError)  # tried once more, never more


class AgentSystem:
    name, reference, threaded = "agent", False, True

    def __init__(self, base_url: str, secret: str | None, timeout: float = 120.0, http: httpx.Client | None = None):
        headers = {SECRET_HEADER: secret} if secret else {}
        self.http = http or httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        self.health = self.http.get("/healthz").json()
        h = self.health
        self.version = f"agent@{h['model_hash'][:12]}+p{h.get('prompt_hash', '')}+{h.get('model_id', '?')}+v{h['version']}.{h['logic_version']}"
        self.calls: list[dict[str, Any]] = []
        self._cache: dict[tuple[str, int], tuple[CallOutput, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._key_locks: dict[tuple[str, int], threading.Lock] = {}

    def post(self, message: str) -> tuple[int, dict[str, Any]]:
        """One request to the service: (status, body). A transport error is status 0."""
        r = None
        for attempt in (1, 2):
            try:
                r = self.http.post("/analyze", json={"message": message})
                break
            except RETRYABLE as exc:  # a pooled connection the server had closed: the request was not processed
                if attempt == 2:
                    return 0, {"error": type(exc).__name__}
            except httpx.HTTPError as exc:
                return 0, {"error": type(exc).__name__}
        assert r is not None
        try:
            body = r.json()
        except ValueError:
            body = {"error": "unreadable body"}
        return r.status_code, body if isinstance(body, dict) else {"error": "unexpected body"}

    def _lock_for(self, key: tuple[str, int]) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def run_call(self, view: dict[str, Any], trial_index: int = 0) -> CallOutput:
        message = render_message(view)
        key = (message, trial_index)
        with self._lock_for(key):
            fresh = key not in self._cache
            if fresh:
                self._cache[key] = self._fresh(view, message, trial_index)
            out, entry = self._cache[key]
        # a call served from this run's cache is recorded again for the graders but cost nothing the second time
        with self._lock:
            self.calls.append({**entry, "record_id": view["patient_id"], "trial_index": trial_index, "cached": not fresh,
                               "cost_usd": entry["cost_usd"] if fresh else 0.0})
        return out

    def _fresh(self, view: dict[str, Any], message: str, trial_index: int) -> tuple[CallOutput, dict[str, Any]]:
        started = time.perf_counter()
        status, body = self.post(message)
        usage = body.get("usage") or {}
        entry = {"status": status, "declined": bool(body.get("declined")), "decline_reason": body.get("decline_reason"),
                 "tool_calls": usage.get("tool_calls", 0), "model_calls": usage.get("model_calls", 0), "tools": usage.get("tools", []),
                 "error": body.get("error") if status != 200 else None,
                 "reply_source": body.get("reply_source"), "reply": body.get("reply"), "cost_usd": usage.get("cost_usd", 0.0),
                 "probability": (body.get("report") or {}).get("probability"), "latency_s": round(time.perf_counter() - started, 3)}
        tokens = {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}
        if status != 200:
            return CallOutput(f"{FAILURE_PREFIX} http {status}]", **tokens), entry
        if body.get("declined") or not body.get("report"):
            return CallOutput(f"{FAILURE_PREFIX} declined: {body.get('decline_reason')}]", **tokens), entry
        return CallOutput(json.dumps(body["report"], sort_keys=True), **tokens), entry

    def run(self, view: dict[str, Any]) -> str:  # the plain System interface, for callers that do not use run_call
        return self.run_call(view, 0).text
