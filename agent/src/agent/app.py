"""The chat service: ``POST /analyze``, ``POST /packet`` and ``GET /healthz``, with every guard applied before the model is called."""

from __future__ import annotations

import hmac
import json
import math
import time
import unicodedata
import uuid
from typing import Any, Callable

import risk_model
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from risk_model import intake, policy, scan, summary
from risk_model.report import DISCLAIMER
from starlette.concurrency import run_in_threadpool

from . import guard, precheck, pricing, replies
from .config import Settings
from .logs import log_request
from .orchestrator import Orchestrator, OrchestratorError
from .store import StoreError
from .limits import build_estimate_limiter, build_limits
from .summarizer import PACKET_PROMPT_HASH, Summarizer, SummarizerError

VERSION = "0.1.0"
SECRET_HEADER = "x-shared-secret"
VISITOR_HEADER = "x-visitor-address"
MAX_BODY_BYTES = 64 * 1024  # a body this large is refused before it is read, whatever the message cap is
PACKET_KEYS = {"message", "attestations"}
ESTIMATE_KEYS = {"labs", "symptoms"}


def clean(message: str) -> str:
    """Line breaks and tabs stay; other control characters are removed."""
    message = message.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(c for c in message if c in "\n\t" or unicodedata.category(c) != "Cc")


def create_app(settings: Settings, orchestrator: Orchestrator, clock: Callable[[], float] = time.time, limits: Any = None,
               summarizer: Summarizer | None = None, estimate_limiter: Any = None) -> FastAPI:
    app = FastAPI(title="Fictional-disease risk chat", docs_url=None, redoc_url=None, openapi_url=None)
    limiter, spend = limits or build_limits(settings, clock)
    estimate_limit = estimate_limiter or build_estimate_limiter(settings, clock)
    model_hash = risk_model.model_hash(settings.model_dir)
    risk = risk_model.load(settings.model_dir)
    secret = settings.shared_secret.encode() if settings.shared_secret else None

    def reject(status: int, error: str, request_id: str, started: float, size: int = 0, headers: dict[str, str] | None = None,
               logged: str | None = None, **extra: Any) -> JSONResponse:
        log_request(request_id=request_id, status=status, latency_ms=round((time.monotonic() - started) * 1000), message_chars=size,
                    reason=logged or error)
        return JSONResponse({"error": error, "request_id": request_id, **extra}, status_code=status,
                            headers={"x-request-id": request_id, **(headers or {})})

    def client_of(request: Request, authenticated: bool) -> str:
        """Who a request counts against: the address the platform gives, or, for a caller that presented the secret, the visitor it names."""
        if authenticated and request.headers.get(VISITOR_HEADER):
            return request.headers[VISITOR_HEADER][:100]
        return request.client.host if request.client else "unknown"

    async def admit(request: Request, request_id: str, started: float, allowed_keys: set[str] | None = None) -> JSONResponse | tuple[dict[str, Any], str]:
        """Steps every model-backed route shares, in order: the secret, size and shape, the rate limit and the day's spend.
        Returns the refusal, or the parsed body and the cleaned message."""
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
        if not isinstance(message, str) or (allowed_keys is not None and not set(body) <= allowed_keys):
            return reject(422, "invalid_request", request_id, started)
        if len(message) > settings.max_message_chars:
            return reject(413, "message_too_long", request_id, started, len(message), max_chars=settings.max_message_chars)
        message = clean(message)
        if not message.strip():
            return reject(422, "invalid_request", request_id, started, len(message))
        if allowed_keys is PACKET_KEYS:  # answers are checked before any counter or model: a bad one costs nothing
            try:
                scan.check_attestations(body.get("attestations"))
            except ValueError:
                return reject(422, "invalid_request", request_id, started, len(message), logged="invalid_attestations")
        # 3. the rate limit; a caller that presented the secret may name the visitor it is acting for
        client = client_of(request, authenticated)
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
        return body, message

    async def record_spend(request_id: str, cost: float) -> None:
        try:
            await run_in_threadpool(spend.add, cost)
        except StoreError as exc:  # the money is spent and the caller is served; the lost count is logged for the owner
            log_request(request_id=request_id, status=200, reason=f"spend_not_recorded:{exc}", cost_usd=cost)

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "model_hash": model_hash, "version": VERSION, "logic_version": risk_model.LOGIC_VERSION,
                "model_id": orchestrator.model_id, "prompt_hash": getattr(orchestrator, "prompt_hash", ""),
                "packet_prompt_hash": PACKET_PROMPT_HASH, "policy_id": policy.load()["id"]}

    @app.post("/analyze")
    async def analyze(request: Request) -> JSONResponse:
        started, request_id = time.monotonic(), uuid.uuid4().hex
        admitted = await admit(request, request_id, started)
        if isinstance(admitted, JSONResponse):
            return admitted
        _, message = admitted
        try:
            outcome = await run_in_threadpool(orchestrator.run, message)
        except OrchestratorError as exc:
            # the class of the failure (never its text) goes to the log; the caller gets a generic body
            return reject(502, "model_unavailable", request_id, started, len(message), logged=f"model_unavailable:{exc}")
        cost = pricing.cost_usd(orchestrator.model_id, outcome.input_tokens, outcome.output_tokens)
        await record_spend(request_id, cost)
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

    def shown_summary(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], str, list[str], int, int]:
        """The summary to show, where it came from, the verifier's reason classes, and the tokens spent."""
        template = summary.template_summary(packet)
        if summarizer is None:
            return template, "template", [], 0, 0
        try:
            draft = summarizer.draft(packet)
        except SummarizerError as exc:
            return template, "template", [f"model_failed:{exc}"], 0, 0
        problems = summary.verify(draft.sentences, packet, guard.forbidden)
        if problems:
            return template, "template", sorted({p.split(":")[0] for p in problems}), draft.input_tokens, draft.output_tokens
        return draft.sentences, "model", [], draft.input_tokens, draft.output_tokens

    @app.post("/estimate")
    async def estimate(request: Request) -> JSONResponse:
        """The what-if estimate for hand-set labs and symptoms: no model call, no spend, its own rate limit, no input logged."""
        started, request_id = time.monotonic(), uuid.uuid4().hex

        def refuse(status: int, error: str, headers: dict[str, str] | None = None) -> JSONResponse:
            log_request(request_id=request_id, status=status, route="estimate", reason=error,
                        latency_ms=round((time.monotonic() - started) * 1000))
            return JSONResponse({"error": error, "request_id": request_id}, status_code=status, headers={"x-request-id": request_id, **(headers or {})})

        authenticated = False
        if secret is not None:
            if not hmac.compare_digest(request.headers.get(SECRET_HEADER, "").encode(), secret):
                return refuse(401, "unauthorized")
            authenticated = True
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return refuse(413, "message_too_long")
        try:
            body = json.loads(raw)
        except ValueError:
            return refuse(422, "invalid_request")
        if not isinstance(body, dict) or set(body) != ESTIMATE_KEYS:
            return refuse(422, "invalid_request")
        try:
            wait = await run_in_threadpool(estimate_limit.check, client_of(request, authenticated))
        except StoreError:  # the counters cannot answer: refused, as for the assistant
            return refuse(503, "limits_unavailable")
        if wait is not None:
            return refuse(429, "rate_limited", {"retry-after": str(math.ceil(wait))})
        try:
            out = risk.estimate(body["labs"], body["symptoms"])
        except risk_model.EstimateError:
            return refuse(422, "invalid_request")
        log_request(request_id=request_id, status=200, route="estimate", latency_ms=round((time.monotonic() - started) * 1000))
        return JSONResponse({"request_id": request_id, "probability": out["probability"], "band": out["band"], "score": out["score"],
                             "start": out["start"], "breakdown": out["breakdown"], "message": out["message"], "model_hash": model_hash},
                            headers={"x-request-id": request_id})

    @app.post("/packet")
    async def packet(request: Request) -> JSONResponse:
        started, request_id = time.monotonic(), uuid.uuid4().hex
        admitted = await admit(request, request_id, started, PACKET_KEYS)
        if isinstance(admitted, JSONResponse):
            return admitted
        body, message = admitted
        # the guards decline what the chat agent declines, in code, before anything is scored or paid for
        kind, reason = precheck.decide_chart(message)
        if kind == "decline":
            log_request(request_id=request_id, status=200, route="packet", tool="decline", reason=reason,
                        latency_ms=round((time.monotonic() - started) * 1000), message_chars=len(message))
            return JSONResponse({"request_id": request_id, "declined": True, "decline_reason": reason,
                                 "message": replies.decline_text(reason)}, headers={"x-request-id": request_id})
        report = risk.report(intake.view_from_text(message))
        built = scan.evaluate(intake.view_from_text(message), report, body.get("attestations"))
        sentences, source, failures, tokens_in, tokens_out = await run_in_threadpool(shown_summary, built)
        model_id = summarizer.model_id if summarizer is not None else "scripted"
        cost = pricing.cost_usd(model_id, tokens_in, tokens_out)
        await record_spend(request_id, cost)
        usage = {"input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": cost, "model_calls": 1 if tokens_in else 0}
        log_request(request_id=request_id, status=200, route="packet", summary_source=source, input_tokens=tokens_in,
                    output_tokens=tokens_out, cost_usd=cost, latency_ms=round((time.monotonic() - started) * 1000),
                    message_chars=len(message), verifier_failures=",".join(failures), model_calls=usage["model_calls"])
        return JSONResponse({"request_id": request_id, "declined": False, "policy_id": built["policy_id"],
                             "notice": policy.load()["notice"], "criteria": built["criteria"], "evidence": built["evidence"],
                             "gaps": built["gaps"], "summary": sentences, "summary_source": source,
                             "summary_fallback": failures, "report": report, "disclaimer": DISCLAIMER, "usage": usage},
                            headers={"x-request-id": request_id})

    return app
