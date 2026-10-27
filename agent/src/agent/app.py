"""The chat service: ``POST /analyze`` and ``GET /healthz``, with every guard applied before the model is called."""

from __future__ import annotations

import hmac
import math
import time
import unicodedata
import uuid
from typing import Any, Callable

import risk_model
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import pricing, replies
from .config import Settings
from .logs import log_request
from .orchestrator import Orchestrator, OrchestratorError
from .store import StoreError
from .limits import build_limits

VERSION = "0.1.0"
SECRET_HEADER = "x-shared-secret"
VISITOR_HEADER = "x-visitor-address"
MAX_BODY_BYTES = 64 * 1024  # a body this large is refused before it is read, whatever the message cap is


def clean(message: str) -> str:
    """Line breaks and tabs stay; other control characters are removed."""
    message = message.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(c for c in message if c in "\n\t" or unicodedata.category(c) != "Cc")


def create_app(settings: Settings, orchestrator: Orchestrator, clock: Callable[[], float] = time.time, limits: Any = None) -> FastAPI:
    app = FastAPI(title="Fictional-disease risk chat", docs_url=None, redoc_url=None, openapi_url=None)
    limiter, spend = limits or build_limits(settings, clock)
    model_hash = risk_model.model_hash(settings.model_dir)
    secret = settings.shared_secret.encode() if settings.shared_secret else None

    def reject(status: int, error: str, request_id: str, started: float, size: int = 0, headers: dict[str, str] | None = None,
               logged: str | None = None, **extra: Any) -> JSONResponse:
        log_request(request_id=request_id, status=status, latency_ms=round((time.monotonic() - started) * 1000), message_chars=size,
                    reason=logged or error)
        return JSONResponse({"error": error, "request_id": request_id, **extra}, status_code=status,
                            headers={"x-request-id": request_id, **(headers or {})})

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "model_hash": model_hash, "version": VERSION, "logic_version": risk_model.LOGIC_VERSION,
                "model_id": orchestrator.model_id, "prompt_hash": getattr(orchestrator, "prompt_hash", "")}

    @app.post("/analyze")
    async def analyze(request: Request) -> JSONResponse:
        started, request_id = time.monotonic(), uuid.uuid4().hex
        # 1. the shared secret, in constant time, before anything else is read
        authenticated = False
        if secret is not None:
            sent = request.headers.get(SECRET_HEADER, "").encode()
            if not hmac.compare_digest(sent, secret):
                return reject(401, "unauthorized", request_id, started)
            authenticated = True
        # 2. size and shape
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            return reject(413, "message_too_long", request_id, started, max_chars=settings.max_message_chars)
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return reject(413, "message_too_long", request_id, started, max_chars=settings.max_message_chars)
        try:
            body = await request.json()
        except ValueError:
            return reject(422, "invalid_request", request_id, started)
        message = body.get("message") if isinstance(body, dict) else None
        if not isinstance(message, str):
            return reject(422, "invalid_request", request_id, started)
        if len(message) > settings.max_message_chars:
            return reject(413, "message_too_long", request_id, started, len(message), max_chars=settings.max_message_chars)
        message = clean(message)
        if not message.strip():
            return reject(422, "invalid_request", request_id, started, len(message))
        # 3. the rate limit; a caller that presented the secret may name the visitor it is acting for
        client = request.client.host if request.client else "unknown"
        if authenticated and request.headers.get(VISITOR_HEADER):
            client = request.headers[VISITOR_HEADER][:100]
        try:  # the counters may be in a remote store: off the event loop, and if they cannot answer the request is refused
            wait = await run_in_threadpool(limiter.check, client)
            if wait is not None:
                return reject(429, "rate_limited", request_id, started, len(message), {"retry-after": str(math.ceil(wait))})
            # 4. the day's spend
            exhausted = await run_in_threadpool(spend.exhausted)
        except StoreError as exc:
            return reject(503, "limits_unavailable", request_id, started, len(message), logged=f"limits_unavailable:{exc}")
        if exhausted:
            return reject(503, "daily_budget_used", request_id, started, len(message))
        try:
            outcome = await run_in_threadpool(orchestrator.run, message)
        except OrchestratorError as exc:
            # the class of the failure (never its text) goes to the log; the caller gets a generic body
            return reject(502, "model_unavailable", request_id, started, len(message), logged=f"model_unavailable:{exc}")
        cost = pricing.cost_usd(orchestrator.model_id, outcome.input_tokens, outcome.output_tokens)
        try:
            await run_in_threadpool(spend.add, cost)
        except StoreError as exc:  # the money is spent and the caller is served; the lost count is logged for the owner
            log_request(request_id=request_id, status=200, reason=f"spend_not_recorded:{exc}", cost_usd=cost)
        if outcome.tool == "score" and outcome.report is not None:
            reply = replies.finalize_scored(outcome.report, outcome.reply)
            declined, report, reason = False, outcome.report, None
        else:  # a decline, or a model that called neither tool: never the model's own prose
            reason = outcome.decline_reason if outcome.tool == "decline" else "out_of_scope"
            reply, declined, report = replies.finalize_declined(reason), True, None
        usage = {"input_tokens": outcome.input_tokens, "output_tokens": outcome.output_tokens, "cost_usd": cost,
                 "tool_calls": outcome.tool_calls, "model_calls": outcome.model_calls, "tools": list(outcome.tool_names)}
        log_request(request_id=request_id, status=200, tool=outcome.tool or "none", reply_source=reply.source,
                    input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens, cost_usd=cost,
                    latency_ms=round((time.monotonic() - started) * 1000), message_chars=len(message),
                    tool_calls=outcome.tool_calls, model_calls=outcome.model_calls, prompt_hash=outcome.prompt_hash,
                    tools=",".join(outcome.tool_names))
        return JSONResponse({"request_id": request_id, "declined": declined, "decline_reason": reason, "reply": reply.text,
                             "reply_source": reply.source, "report": report, "usage": usage},
                            headers={"x-request-id": request_id})

    return app
