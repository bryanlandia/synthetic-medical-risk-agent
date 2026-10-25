"""Browser-mode review against the real rating app, with a scripted model (no API calls, no cost)."""

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from data_gen.config import GenConfig, LLMConfig  # noqa: E402
from data_gen.labs import SYMPTOM_KEYS  # noqa: E402
from data_gen.llm.gate import evaluate, load_round  # noqa: E402
from data_gen.llm.gateway import Budget  # noqa: E402
from data_gen.llm.ratings import read_rating_file  # noqa: E402
from data_gen.review.browser import (TOOL_NAMES, TOOLS, AppServer, BrowserTools, ToolUse, Turn,  # noqa: E402
                                     browser_reviewer_name)
from data_gen.review import browser as _browser  # noqa: E402
import functools  # noqa: E402

run_browser_review = functools.partial(_browser.run_browser_review, pause=0)  # tests do not need to dwell

from test_llm_gate import LABEL_OF, items, pilot  # noqa: E402,F401  (fixtures)

APP_DIR = Path(__file__).resolve().parents[2] / "rating_ui"
needs_app = pytest.mark.skipif(
    not (APP_DIR / ".next" / "BUILD_ID").exists() or shutil.which("npx") is None,
    reason="build the rating app first: cd rating_ui && npm install && npm run build")

CFG = GenConfig(note_source="llm", seed=7, llm=LLMConfig(reviewer_max_steps=500, concurrency=2,
                                                          gate_rater_kinds=["human", "llm"]))


class Script:
    """A scripted 'model': reads the note id from the user message and answers with tool calls."""

    def __init__(self, key, sheet, plausible=lambda meta: "y", extra=None):
        self.key = key
        self.id_of = {n["text"]: n["id"] for n in sheet["notes"]}
        self.plausible = plausible
        self.extra = extra or {}
        self.turns = 0
        self.systems: set[str] = set()

    def step(self, *, system, messages, tools, model, max_tokens):
        self.turns += 1
        self.systems.add(system)
        first = messages[0]["content"]
        text = first.split('"""\n', 1)[1].rsplit('\n"""', 1)[0]
        note_id = self.id_of[text]
        meta = self.key[note_id]
        uses = []
        n = [0]

        def use(name, **args):
            n[0] += 1
            uses.append(ToolUse(f"t{self.turns}-{n[0]}", name, args))

        if len(messages) == 1:  # first turn for this note: rate it
            for fn in self.extra.get(note_id, []):
                use(*fn[0], **fn[1])
            verdict = self.plausible(meta)
            use("set_plausible", value=verdict)
            for k in SYMPTOM_KEYS:
                label = LABEL_OF[meta["extraction"][k]] if meta["kind"] == "note" else "none"
                use("set_symptom", symptom=k, value=label)
            if verdict == "n":
                use("add_comment", text="reads like boilerplate")
        else:  # second turn: move on (or finish on the last note)
            last = note_id == sorted(self.key)[-1]
            use("finish" if last else "next_note")
        return Turn(uses, [{"type": "tool_use", "id": u.id, "name": u.name, "input": u.input} for u in uses],
                    "tool_use", 1200, 150)


@pytest.fixture
def setup(pilot, tmp_path):
    _, directory, _ = pilot
    d = tmp_path / "round0"
    d.mkdir()
    for name in ("sheet.json", "key.json"):
        (d / name).write_text((directory / name).read_text())
    key = json.loads((d / "key.json").read_text())["notes"]
    sheet = json.loads((d / "sheet.json").read_text())
    return d, key, sheet


def budget():
    return Budget(10_000, 100.0, 2.0, 10.0)


def test_the_fixed_tool_set():
    assert TOOL_NAMES == {"read_note", "set_plausible", "set_symptom", "add_comment", "next_note", "finish"}
    assert all(t["input_schema"]["type"] == "object" for t in TOOLS)


@needs_app
def test_scripted_session_writes_a_complete_llm_file_and_a_video(setup):
    d, key, sheet = setup
    script = Script(key, sheet, plausible=lambda m: "y" if m["kind"] == "note" else "n")
    with AppServer(APP_DIR, d, CFG) as app:
        result = run_browser_review(CFG, script, budget(), d, app.url, max_notes=88)
    assert result.stopped is None and result.refused == 0
    rf = read_rating_file(d / f"ratings.{browser_reviewer_name(CFG)}.json")  # written by the app itself
    assert rf.kind == "llm" and rf.model_id == "claude-sonnet-5-5" and len(rf.ratings) == 88
    assert all(r.complete for r in rf.ratings.values())
    assert result.video and result.video.stat().st_size > 1000 and result.video.suffix == ".webm"
    lines = [json.loads(l) for l in (d / "review-session.jsonl").read_text().splitlines()]
    assert lines[-1]["event"] == "end" and any(e.get("tool") == "set_symptom" for e in lines)
    assert result.steps == script.turns and script.systems and "tools provided" in next(iter(script.systems))
    loaded, problems = load_round(d, ("llm",))
    report = evaluate(CFG, [loaded], problems)
    assert report.passed, report.render()  # same gate, same thresholds
    assert report.discrimination[browser_reviewer_name(CFG)]["gap"] == 1.0


# --- 4.1 the fixed tool set is enforced --------------------------------------------------------------------------

@needs_app
def test_actions_outside_the_set_and_bad_arguments_are_refused_and_counted(setup):
    d, key, sheet = setup
    first = sheet["notes"][0]["id"]
    extra = {first: [(("open_url",), {"url": "http://example.com"}), (("navigate",), {"url": "file:///etc/passwd"}),
                     (("set_symptom",), {"symptom": "tremor", "value": "severe"}),
                     (("set_plausible",), {"value": "maybe"}), (("add_comment",), {"text": ""})]}
    script = Script(key, sheet, extra=extra)
    with AppServer(APP_DIR, d, CFG) as app:
        result = run_browser_review(CFG, script, budget(), d, app.url, max_notes=2, record_video=False)
    assert result.refused == 5 and result.stopped is None
    events = [json.loads(l) for l in (d / "review-session.jsonl").read_text().splitlines()]
    refusals = [e for e in events if e.get("outcome") == "refused"]
    assert {r["tool"] for r in refusals} == {"open_url", "navigate", "set_symptom", "set_plausible", "add_comment"}
    rf = read_rating_file(d / f"ratings.{browser_reviewer_name(CFG)}.json")
    assert rf.ratings[first].complete  # the refused actions changed nothing; the valid ones then worked


@needs_app
def test_moving_on_from_an_incomplete_note_is_rejected_not_silently_accepted(setup):
    d, key, sheet = setup
    first = sheet["notes"][0]["id"]
    script = Script(key, sheet, extra={first: [(("next_note",), {})]})  # tries to leave before rating
    with AppServer(APP_DIR, d, CFG) as app:
        result = run_browser_review(CFG, script, budget(), d, app.url, max_notes=2, record_video=False)
    assert result.rejected == 1 and result.refused == 0
    rf = read_rating_file(d / f"ratings.{browser_reviewer_name(CFG)}.json")
    assert all(r.complete for r in rf.ratings.values())


@needs_app
def test_requests_outside_the_local_app_are_blocked_and_counted(setup):
    from playwright.sync_api import sync_playwright
    from data_gen.review.browser import SessionLog, install_request_guard

    d, key, sheet = setup
    session = SessionLog(d / "s.jsonl")
    with AppServer(APP_DIR, d, CFG) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context()
        install_request_guard(ctx, app.url, session)
        page = ctx.new_page()
        page.goto(app.url)
        page.get_by_test_id("note-id").wait_for()
        outcome = page.evaluate("fetch('http://example.com/leak').then(() => 'reached', () => 'blocked')")
        browser.close()
    assert outcome == "blocked" and session.blocked_requests == ["http://example.com/leak"]


def test_the_page_state_tools_never_reach_the_key():
    from data_gen.review.browser import BrowserTools

    src = Path(BrowserTools.__init__.__code__.co_filename).read_text()
    assert "key.json" not in src


# --- 4.3 limits keep partial work ------------------------------------------------------------------------------------

def assert_partial(d, result, expected_min, expected_max):
    rf = read_rating_file(d / f"ratings.{browser_reviewer_name(CFG)}.json")
    assert expected_min <= len(rf.ratings) <= expected_max
    assert result.stopped
    assert result.video and result.video.exists() and result.video.stat().st_size > 0  # the video is still saved
    loaded, problems = load_round(d, ("llm",))
    report = evaluate(CFG, [loaded], problems)
    assert not report.passed and any("have a plausible rating" in p for p in report.problems)
    return rf


@needs_app
def test_step_limit_keeps_partial_ratings_and_the_video(setup):
    d, key, sheet = setup
    cfg = GenConfig(note_source="llm", seed=7, llm=LLMConfig(reviewer_max_steps=10, gate_rater_kinds=["llm"]))
    with AppServer(APP_DIR, d, cfg) as app:
        result = run_browser_review(cfg, Script(key, sheet), budget(), d, app.url)
    assert "step limit" in result.stopped and result.steps == 10
    assert_partial(d, result, 5, 6)


@needs_app
def test_call_cap_keeps_partial_ratings_and_the_video(setup):
    d, key, sheet = setup
    with AppServer(APP_DIR, d, CFG) as app:
        result = run_browser_review(CFG, Script(key, sheet), Budget(7, 100.0, 2.0, 10.0), d, app.url)
    assert "call cap reached" in result.stopped and result.steps == 7
    assert_partial(d, result, 3, 5)


@needs_app
def test_spend_cap_keeps_partial_ratings_and_the_video(setup):
    d, key, sheet = setup
    one_turn = (1200 * 2.0 + 150 * 10.0) / 1_000_000  # what the scripted turns cost
    with AppServer(APP_DIR, d, CFG) as app:
        result = run_browser_review(CFG, Script(key, sheet), Budget(10_000, one_turn * 4.5, 2.0, 10.0), d, app.url)
    assert "spend cap reached" in result.stopped and result.steps == 5
    assert_partial(d, result, 2, 4)


# --- the command ------------------------------------------------------------------------------------------------------------

def test_browser_estimate_needs_no_key_no_app_and_no_browser(setup, monkeypatch, capsys):
    from data_gen.cli import main

    d, _, _ = setup
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code = main(["review", "--dir", str(d.parent), "--note-source", "llm", "--mode", "browser", "--max-notes", "12",
                 "--estimate"])
    out = capsys.readouterr().out
    assert code == 0 and "mode: browser" in out and "model turns" in out and "estimated cost" in out
    assert main(["review", "--dir", str(d.parent), "--note-source", "llm", "--mode", "browser"]) == 4  # needs --yes


@needs_app
def test_command_runs_a_short_recorded_session(setup, monkeypatch, capsys):
    from data_gen.cli import main

    d, key, sheet = setup
    monkeypatch.setattr("data_gen.review.browser.AnthropicToolClient", lambda **k: Script(key, sheet))
    code = main(["review", "--dir", str(d.parent), "--note-source", "llm", "--mode", "browser", "--max-notes", "3",
                 "--yes", "--pause", "0", "--app-dir", str(APP_DIR)])
    out = capsys.readouterr().out
    assert code == 0 and "3 notes visited" in out and "video:" in out
    assert (d / "review.webm").stat().st_size > 0 and (d / "review-session.jsonl").exists()
    assert len(read_rating_file(d / f"ratings.{browser_reviewer_name(GenConfig(note_source='llm'))}.json").ratings) == 3


def test_without_a_key_the_command_stops_before_opening_a_browser(setup, monkeypatch, capsys):
    from data_gen.cli import main

    d, _, _ = setup
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code = main(["review", "--dir", str(d.parent), "--note-source", "llm", "--mode", "browser", "--yes",
                 "--app-dir", "/nonexistent"])
    assert code == 2 and "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_the_tool_client_sends_a_plain_tool_request_and_reads_tool_calls(monkeypatch):
    from types import SimpleNamespace as NS

    from data_gen.review.browser import AnthropicToolClient

    sent = {}

    class Messages:
        def create(self, **kw):
            sent.update(kw)
            blocks = [NS(type="thinking", thinking="..."), NS(type="tool_use", id="tu1", name="set_plausible", input={"value": "y"})]
            return NS(content=blocks, stop_reason="tool_use", usage=NS(input_tokens=900, output_tokens=120))

    class SDK:
        class Anthropic:
            def __init__(self, **kw):
                self.messages = Messages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    turn = AnthropicToolClient(effort="medium", sdk=SDK).step(
        system="s", messages=[{"role": "user", "content": "x"}], tools=TOOLS, model="claude-sonnet-5-5", max_tokens=100)
    assert [(u.name, u.input) for u in turn.tool_uses] == [("set_plausible", {"value": "y"})]
    assert len(turn.content) == 2  # the thinking block is kept whole for the next turn
    assert (turn.input_tokens, turn.output_tokens) == (900, 120)
    assert sent["output_config"] == {"effort": "medium"} and sent["tools"] == TOOLS
    for rejected in ("tool_choice", "temperature", "top_p", "top_k"):
        assert rejected not in sent


# --- the recording is readable ---------------------------------------------------------------------------------------------

@needs_app
def test_the_note_and_comment_are_in_view_at_the_top_of_the_page(setup):
    from playwright.sync_api import sync_playwright

    d, key, sheet = setup
    with AppServer(APP_DIR, d, CFG) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.goto(app.url)
        page.get_by_test_id("note-id").wait_for()
        tools = BrowserTools(page, _browser.SessionLog(d / "s.jsonl"), 88)
        tools.call("set_plausible", {"value": "n"})
        tools.call("add_comment", {"text": "Mechanical, redundant symptom denials with synonym padding in every line."})
        page.evaluate("window.scrollTo(0, 0)")
        for tid in ("notice", "note-id", "note-text", "comment", "progress"):
            box = page.get_by_test_id(tid).bounding_box()
            assert box and box["y"] >= 0 and box["y"] + min(box["height"], 60) <= 1000, tid
        browser.close()


@needs_app
def test_the_reviewer_dwells_on_each_finished_note_and_comment(setup):
    import time

    d, key, sheet = setup
    script = Script(key, sheet, plausible=lambda m: "n")  # an n carries a comment too
    with AppServer(APP_DIR, d, CFG) as app:
        t0 = time.monotonic()
        _browser.run_browser_review(CFG, script, budget(), d, app.url, max_notes=1, record_video=False, pause=0)
        quick = time.monotonic() - t0
    shutil.rmtree(d / "ratings.reviewer-claude-sonnet-5-5-browser.json", ignore_errors=True)
    (d / f"ratings.{browser_reviewer_name(CFG)}.json").unlink(missing_ok=True)
    with AppServer(APP_DIR, d, CFG) as app:
        t0 = time.monotonic()
        _browser.run_browser_review(CFG, script, budget(), d, app.url, max_notes=1, record_video=False, pause=2.0)
        slow = time.monotonic() - t0
    assert slow - quick >= 3.0  # about 1s on arrival + 2s after the comment + 2s before moving on, minus noise
