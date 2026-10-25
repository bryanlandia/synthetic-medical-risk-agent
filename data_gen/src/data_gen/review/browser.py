"""Browser-mode review: the reviewer operates the real rating app through a fixed set of tools, on video.

Playwright drives the page (clicks and typing on the app's test ids), so the app itself writes the rating file
through its normal save path. The model never gets a free browser: it can only call the tools below, and every
network request outside the local app is blocked and counted.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ..config import GenConfig
from ..labs import SYMPTOM_KEYS
from ..llm.client import LLMResult
from ..llm.gateway import Budget, BudgetExceeded
from .prompt import REVIEWER_SYSTEM_UI
from .reviewer import reviewer_name


def browser_reviewer_name(cfg: GenConfig) -> str:
    """Browser sessions are a rater of their own, so they never mix with a direct-mode file."""
    return f"{reviewer_name(cfg)}-browser"

log = logging.getLogger("data_gen.review")

SYMPTOM_VALUES = ("present", "possible", "absent", "none")
MAX_TURNS_PER_NOTE = 8
MAX_COMMENT_CHARS = 500

TOOLS: list[dict[str, Any]] = [
    {"name": "read_note", "description": "Read the note currently on screen and the ratings already set for it.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "set_plausible", "description": "Say whether the note reads like real clinical documentation.",
     "input_schema": {"type": "object", "properties": {"value": {"type": "string", "enum": ["y", "n"]}},
                      "required": ["value"]}},
    {"name": "set_symptom", "description": "Say how the NOTE describes one symptom.",
     "input_schema": {"type": "object", "properties": {
         "symptom": {"type": "string", "enum": list(SYMPTOM_KEYS)},
         "value": {"type": "string", "enum": list(SYMPTOM_VALUES)}}, "required": ["symptom", "value"]}},
    {"name": "add_comment", "description": "Write a short comment for this note (give the reason when you say n).",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "next_note", "description": "Go to the next note. Only works when this note is completely rated.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "finish", "description": "Finish the round. Use on the last note, once every note is rated.",
     "input_schema": {"type": "object", "properties": {}}},
]
TOOL_NAMES = {t["name"] for t in TOOLS}


@dataclass
class SessionLog:
    path: Path
    refused: int = 0  # actions outside the fixed set or with invalid arguments
    rejected: int = 0  # valid actions the app could not accept yet (an incomplete note)
    blocked_requests: list[str] = field(default_factory=list)

    def write(self, **event: Any) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(event, sort_keys=True, default=str) + "\n")


class BrowserTools:
    """The reviewer's hands: each tool maps to fixed actions on the app's test ids."""

    def __init__(self, page: Any, session: SessionLog, total_notes: int, pause: float = 0.0,
                 order: list[str] | None = None):
        self.page, self.session, self.total = page, session, total_notes
        self.order = order  # the notes to visit, in order, when only a sample is rated; None = all, in sheet order
        self.pause = pause  # seconds to dwell where a viewer of the recording needs to read the page
        self.finished = False

    def show(self, seconds: float) -> None:
        """Scroll to the top of the page (the note, the ratings and the comment are all in view there) and dwell."""
        if seconds <= 0:
            return
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(int(seconds * 1000))

    # ---- reading -----------------------------------------------------------------------------
    def state(self) -> dict:
        p = self.page
        pressed = lambda tid: p.get_by_test_id(tid).get_attribute("aria-pressed") == "true"  # noqa: E731
        plausible = next((v for v in ("y", "n") if pressed(f"plausible-{v}")), None)
        symptoms = {k: next((v for v in SYMPTOM_VALUES if pressed(f"symptom-{k}-{v}")), None) for k in SYMPTOM_KEYS}
        return {
            "note_id": p.get_by_test_id("note-id").inner_text().split()[0],
            "text": p.get_by_test_id("note-text").inner_text(),
            "plausible": plausible, "symptoms": symptoms,
            "comment": p.get_by_test_id("comment").input_value(),
            "progress": p.get_by_test_id("progress").inner_text(),
        }

    def describe(self) -> str:
        s = self.state()
        missing = [k for k, v in s["symptoms"].items() if v is None] + (["plausible"] if s["plausible"] is None else [])
        return (f"Note {s['note_id']} ({s['progress']}):\n\"\"\"\n{s['text']}\n\"\"\"\n"
                f"Set so far: plausible={s['plausible']}, symptoms={s['symptoms']}, comment={s['comment']!r}. "
                f"Missing: {', '.join(missing) or 'nothing'}.")

    # ---- acting --------------------------------------------------------------------------------
    def call(self, name: str, args: dict) -> tuple[str, str]:
        """Run one tool call. Returns (result text, outcome) with outcome 'ok', 'refused' or 'rejected'."""
        if name not in TOOL_NAMES or not isinstance(args, dict):
            self.session.refused += 1
            return f"refused: {name!r} is not one of the available tools ({', '.join(sorted(TOOL_NAMES))})", "refused"
        try:
            return getattr(self, f"_tool_{name}")(**args), "ok"
        except _Refused as exc:
            self.session.refused += 1
            return f"refused: {exc}", "refused"
        except _Rejected as exc:
            self.session.rejected += 1
            return f"not done: {exc}", "rejected"
        except TypeError:
            self.session.refused += 1
            return f"refused: wrong arguments for {name}", "refused"

    def _saved(self) -> None:
        self.page.get_by_test_id("save-state").filter(has_text="Saved").wait_for(timeout=20_000)

    def _tool_read_note(self) -> str:
        return self.describe()

    def _tool_set_plausible(self, value: str) -> str:
        if value not in ("y", "n"):
            raise _Refused("value must be y or n")
        self.page.get_by_test_id(f"plausible-{value}").click()
        self._saved()
        return f"plausible set to {value}"

    def _tool_set_symptom(self, symptom: str, value: str) -> str:
        if symptom not in SYMPTOM_KEYS or value not in SYMPTOM_VALUES:
            raise _Refused(f"symptom must be one of {', '.join(SYMPTOM_KEYS)}; value one of {', '.join(SYMPTOM_VALUES)}")
        self.page.get_by_test_id(f"symptom-{symptom}-{value}").click()
        self._saved()
        return f"{symptom} set to {value}"

    def _tool_add_comment(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_COMMENT_CHARS:
            raise _Refused(f"comment must be 1 to {MAX_COMMENT_CHARS} characters")
        box = self.page.get_by_test_id("comment")
        box.fill(text.strip())
        box.blur()
        self._saved()
        self.show(self.pause)  # let a viewer read the comment
        return "comment saved"

    def _incomplete(self) -> list[str]:
        s = self.state()
        missing = [k for k, v in s["symptoms"].items() if v is None] + (["plausible"] if s["plausible"] is None else [])
        if s["plausible"] == "n" and not s["comment"].strip():
            missing.append("a reason (add_comment) for the n")
        return missing

    def _tool_next_note(self) -> str:
        if missing := self._incomplete():
            raise _Rejected(f"this note is not complete yet; missing: {', '.join(missing)}")
        before = self.page.get_by_test_id("note-id").inner_text()
        if self.order is not None:
            here = before.split()[0]
            at = self.order.index(here) if here in self.order else -1
            if at == len(self.order) - 1:
                raise _Rejected("this is the last note; call finish instead")
            self.show(self.pause)  # the finished note, ratings and comment stay on screen before moving on
            self.page.get_by_test_id(f"chip-{self.order[at + 1]}").click()  # jump to the next note of the sample
        else:
            button = self.page.get_by_test_id("next")
            if button.is_disabled():
                raise _Rejected("this is the last note; call finish instead")
            self.show(self.pause)
            button.click()
        self.page.wait_for_function(
            "(b) => document.querySelector('[data-testid=note-id]').innerText !== b", arg=before, timeout=20_000)
        return "moved to the next note"

    def _tool_finish(self) -> str:
        if missing := self._incomplete():
            raise _Rejected(f"this note is not complete yet; missing: {', '.join(missing)}")
        if self.order is not None:
            if self.state()["note_id"] != self.order[-1]:
                raise _Rejected("there are more notes to rate; call next_note")
        elif self.page.get_by_test_id("finished").count() == 0:
            n = self.page.get_by_test_id("incomplete-count").inner_text()
            raise _Rejected(f"the round is not finished: {n}")
        self.show(self.pause)
        self.finished = True
        return "round finished"


class _Refused(Exception):
    pass


class _Rejected(Exception):
    pass


# ---- the model side ----------------------------------------------------------------------------

@dataclass
class ToolUse:
    id: str
    name: str
    input: dict


@dataclass
class Turn:
    tool_uses: list[ToolUse]
    content: Any  # what to send back as the assistant message (SDK blocks, kept whole)
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    text: str = ""


class ToolClient(Protocol):
    def step(self, *, system: str, messages: list[dict], tools: list[dict], model: str, max_tokens: int) -> Turn: ...


class AnthropicToolClient:
    """Tool-use turns against the Messages API. The key comes only from the environment, as everywhere else."""

    def __init__(self, *, effort: str = "medium", sdk: Any | None = None, timeout: float = 120.0):
        from ..llm.client import API_KEY_ENV, MissingApiKeyError

        key = os.environ.get(API_KEY_ENV)
        if not key:
            raise MissingApiKeyError(f"{API_KEY_ENV} is not set. Export it in your shell before running a review.")
        if sdk is None:
            import anthropic

            sdk = anthropic
        self.effort, self._client = effort, sdk.Anthropic(api_key=key, timeout=timeout)

    def step(self, *, system: str, messages: list[dict], tools: list[dict], model: str, max_tokens: int) -> Turn:
        r = self._client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages,
                                         tools=tools, output_config={"effort": self.effort})
        uses = [ToolUse(b.id, b.name, dict(b.input)) for b in r.content if getattr(b, "type", None) == "tool_use"]
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        return Turn(uses, r.content, r.stop_reason, int(r.usage.input_tokens), int(r.usage.output_tokens), text)


# ---- running a session -----------------------------------------------------------------------------

@dataclass
class BrowserResult:
    rated: int = 0
    steps: int = 0
    stopped: str | None = None
    video: Path | None = None
    session_log: Path | None = None
    refused: int = 0
    rejected: int = 0
    blocked_requests: list[str] = field(default_factory=list)
    notes_attempted: int = 0


def _is_local(url: str, base_url: str) -> bool:
    if url.startswith(("data:", "blob:", "about:")):
        return True
    u, b = urlparse(url), urlparse(base_url)
    return (u.scheme, u.hostname, u.port) == (b.scheme, b.hostname, b.port)


def install_request_guard(ctx: Any, base_url: str, session: SessionLog) -> None:
    """Abort and count every request that leaves the local app."""

    def guard(route):
        if _is_local(route.request.url, base_url):
            route.continue_()
        else:
            session.blocked_requests.append(route.request.url)
            route.abort()

    ctx.route("**/*", guard)


def run_browser_review(
    cfg: GenConfig, tool_client: ToolClient, budget: Budget, round_dir: Path, base_url: str, *,
    max_notes: int | None = None, headless: bool = True, record_video: bool = True, pause: float | None = None,
    note_ids: list[str] | None = None,
) -> BrowserResult:
    """Operate the rating app note by note. A fresh short conversation per note keeps cost linear in the notes."""
    from playwright.sync_api import sync_playwright

    lc = cfg.llm
    round_dir = Path(round_dir)
    out = BrowserResult()
    session = SessionLog(round_dir / "review-session.jsonl")
    session.path.write_text("")
    video_dir = round_dir / "review-video"
    shutil.rmtree(video_dir, ignore_errors=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1000},
                                  record_video_dir=str(video_dir) if record_video else None,
                                  record_video_size={"width": 1280, "height": 1000})

        install_request_guard(ctx, base_url, session)
        page = ctx.new_page()
        try:
            page.goto(base_url)
            page.get_by_test_id("note-id").wait_for(timeout=15_000)
            total = int(page.get_by_test_id("progress").inner_text().split(" of ")[1].split()[0])
            order = list(note_ids) if note_ids else None  # an explicit sample, visited in this order
            tools = BrowserTools(page, session, total, cfg.llm.reviewer_pause_seconds if pause is None else pause, order)
            if order:
                page.get_by_test_id(f"chip-{order[0]}").click()
                page.wait_for_function("(b) => document.querySelector('[data-testid=note-id]').innerText.startsWith(b)",
                                       arg=order[0], timeout=10_000)
            limit = len(order) if order else (min(total, max_notes) if max_notes else total)
            out.stopped = _drive(cfg, tool_client, budget, tools, session, out, limit, total if not order else limit)
        finally:
            video = page.video
            ctx.close()  # the video is finalised on close
            browser.close()
            if record_video and video is not None:
                src = Path(video.path())
                dest = round_dir / "review.webm"
                shutil.move(str(src), dest)
                out.video = dest
            shutil.rmtree(video_dir, ignore_errors=True)
    out.refused, out.rejected = session.refused, session.rejected
    out.blocked_requests = list(session.blocked_requests)
    out.session_log = session.path
    session.write(event="end", steps=out.steps, stopped=out.stopped, refused=out.refused, rejected=out.rejected,
                  blocked_requests=out.blocked_requests, spend_usd=round(budget.spend_usd, 4),
                  video=str(out.video) if out.video else None)
    return out


def _drive(cfg, tool_client, budget, tools: BrowserTools, session: SessionLog, out: BrowserResult,
           limit: int, total: int) -> str | None:
    lc = cfg.llm
    for position in range(limit):
        out.notes_attempted += 1
        tools.show(tools.pause / 2)  # a new note: let a viewer see it at the top of the page
        first = tools.describe()
        messages: list[dict] = [{"role": "user", "content": f"{first}\n\nRate this note, then move on."}]
        done_with_note = False
        for _ in range(MAX_TURNS_PER_NOTE):
            if out.steps >= lc.reviewer_max_steps:
                return f"step limit reached ({lc.reviewer_max_steps} model turns)"
            try:
                budget.reserve()
            except BudgetExceeded as exc:
                return str(exc)
            out.steps += 1
            turn = tool_client.step(system=REVIEWER_SYSTEM_UI, messages=messages, tools=TOOLS, model=lc.reviewer_model_id,
                                    max_tokens=lc.reviewer_max_tokens)
            budget.charge(LLMResult("", turn.input_tokens, turn.output_tokens, turn.stop_reason))
            if turn.stop_reason == "max_tokens":
                session.write(event="truncated", step=out.steps)
                break
            messages.append({"role": "assistant", "content": turn.content})
            if not turn.tool_uses:
                break
            results = []
            for use in turn.tool_uses:
                text, outcome = tools.call(use.name, use.input)
                session.write(event="tool", step=out.steps, note=position + 1, tool=use.name, args=use.input,
                              outcome=outcome, result=text)
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": text,
                                **({"is_error": True} if outcome != "ok" else {})})
                if use.name == "next_note" and outcome == "ok":
                    done_with_note = True
                if use.name == "finish" and outcome == "ok":
                    return None
            messages.append({"role": "user", "content": results})
            if done_with_note:
                break
        if not done_with_note and position < total - 1:
            return f"note {position + 1} could not be completed; stopping"
        if position == limit - 1 and limit < total:
            return None  # asked for fewer notes
    return None


# ---- starting the app -----------------------------------------------------------------------------

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppServer:
    """Start the built rating app for one LLM session and stop it afterwards."""

    def __init__(self, app_dir: Path, round_dir: Path, cfg: GenConfig, port: int | None = None):
        self.app_dir, self.round_dir, self.cfg = Path(app_dir), Path(round_dir), cfg
        self.port = port or free_port()
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "AppServer":
        if not (self.app_dir / ".next" / "BUILD_ID").exists():
            raise RuntimeError(f"{self.app_dir} is not built: run `npm install && npm run build` there first")
        env = {**os.environ, "REALISM_ROUND_DIR": str(self.round_dir.resolve()), "RATER_KIND": "llm",
               "RATER_NAME": browser_reviewer_name(self.cfg), "RATER_MODEL_ID": self.cfg.llm.reviewer_model_id,
               "RATER_PROMPT_VERSION": self.cfg.llm.reviewer_prompt_version}
        self.proc = subprocess.Popen(["npx", "next", "start", "-H", "127.0.0.1", "-p", str(self.port)],
                                     cwd=self.app_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("the rating app exited at startup")
            try:
                urllib.request.urlopen(f"{self.url}/api/session", timeout=2).read()
                return self
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("the rating app did not start within 60 seconds")

    def __exit__(self, *exc) -> None:
        if self.proc and self.proc.poll() is None:
            import signal

            os.killpg(self.proc.pid, signal.SIGTERM)  # npx starts node as a child: stop the whole group
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)


def balanced_note_ids(key_notes: dict, n: int, settings: tuple[str, ...]) -> list[str]:
    """n notes spread evenly over the settings, interleaved, in sheet order within a setting (deterministic).
    Controls are left out. The reviewer never sees this choice or the settings; only the developer's command does."""
    by_setting = {s: sorted(i for i, m in key_notes.items() if m["kind"] == "note" and m["setting"] == s) for s in settings}
    picked: list[str] = []
    cursor = {s: 0 for s in settings}
    while len(picked) < n and any(cursor[s] < len(by_setting[s]) for s in settings):
        for s in settings:
            if len(picked) < n and cursor[s] < len(by_setting[s]):
                picked.append(by_setting[s][cursor[s]])
                cursor[s] += 1
    return picked
