"""Regression tests for the first real pilot: output truncation, silent runs, and runaway retries."""

import io
import json
import logging
import re

import pytest

from data_gen.cli import main
from data_gen.config import GenConfig, LLMConfig
from data_gen.llm.client import LLMResult, MockClient
from data_gen.llm.extractor import EXTRACTOR_SYSTEM
from data_gen.llm.gateway import Budget, CachedClient, DiskCache
from data_gen.llm.pilot import BREAKER_MIN_ATTEMPTED, run_pilot
from data_gen.llm.progress import Progress
from data_gen.llm.run import generate_llm, plan_all
from data_gen.llm.writer import ExclusionTally, NoteWriter, TooManyExclusions

from llm_oracle import OracleLLM
from test_llm_writer import GOOD_EXTRACTION, GOOD_NOTE, plan

CFG = GenConfig(note_source="llm", seed=7, n_train=400, n_test=24, n_per_adversarial_type=4,
                llm=LLMConfig(matched_pairs=6, pilot_per_setting=20))


class Scripted:
    """Returns (text, stop_reason) pairs; the extractor queue is separate."""

    def __init__(self, writer, extractor=()):
        self.writer, self.extractor, self.calls = list(writer), list(extractor), []

    def complete(self, *, system, prompt, model, max_tokens, nonce=0):
        kind = "extractor" if system == EXTRACTOR_SYSTEM else "writer"
        self.calls.append((kind, max_tokens))
        text, stop = (self.extractor if kind == "extractor" else self.writer).pop(0)
        return LLMResult(text, 100, 50, stop)


@pytest.fixture(scope="module")
def items():
    return plan_all(CFG)


def client(oracle, tmp_path):
    return CachedClient(oracle, DiskCache(tmp_path / "c.jsonl"), Budget(100_000, 1000.0, 0.1, 0.5), "1")


# --- truncation: the cause of the first pilot's failures --------------------------------------------------------

def test_default_output_limit_leaves_room_for_thinking():
    assert LLMConfig().max_tokens >= 1500  # 700 truncated most ehr_template notes in the first pilot


def test_a_truncated_note_is_a_failure_even_if_the_text_looks_valid():
    llm = Scripted([(GOOD_NOTE, "max_tokens"), (GOOD_NOTE, "end_turn")], [(GOOD_EXTRACTION, "end_turn")])
    out = NoteWriter(llm, LLMConfig()).write(plan())
    assert out.accepted and out.attempts == 2 and out.failures == [["truncated"]]
    assert [k for k, _ in llm.calls] == ["writer", "writer", "extractor"]  # nothing was spent extracting it


def test_an_empty_truncated_response_is_a_truncation_not_an_empty_note():
    llm = Scripted([("", "max_tokens")] * 3)
    out = NoteWriter(llm, LLMConfig()).write(plan())
    assert not out.accepted and out.failures == [["truncated"]] * 3


def test_a_truncated_extractor_answer_is_retried():
    llm = Scripted([(GOOD_NOTE, "end_turn")] * 2, [('{"tremor": "pre', "max_tokens"), (GOOD_EXTRACTION, "end_turn")])
    out = NoteWriter(llm, LLMConfig()).write(plan())
    assert out.accepted and out.failures == [["extractor_truncated"]]


def test_writer_and_extractor_use_the_configured_limits():
    llm = Scripted([(GOOD_NOTE, "end_turn")], [(GOOD_EXTRACTION, "end_turn")])
    NoteWriter(llm, LLMConfig(max_tokens=1234)).write(plan())
    assert llm.calls[0] == ("writer", 1234) and llm.calls[1][0] == "extractor" and llm.calls[1][1] >= 400


# --- failing fast ----------------------------------------------------------------------------------------------------------

def test_a_failing_setting_is_stopped_early_not_exhausted(items, tmp_path):
    oracle = OracleLLM(items, fail_setting="ehr_template")
    result = run_pilot(CFG, client(oracle, tmp_path), items)
    assert result.aborted.keys() == {"ehr_template"} and result.aborted["ehr_template"] == 1.0
    assert result.short["ehr_template"] == 20
    assert result.tally.attempted("ehr_template") == BREAKER_MIN_ATTEMPTED  # not all ~100 candidates
    assert sum(n.setting == "shorthand" for n in result.notes) == 20  # other settings are unaffected


def test_a_setting_with_occasional_failures_is_not_stopped(items, tmp_path):
    result = run_pilot(CFG, client(OracleLLM(items, fail_setting="ehr_template", fail_every=4), tmp_path), items)
    assert result.aborted == {} and result.short == {}
    assert 0.1 < result.tally.exclusion_rate("ehr_template") < 0.5


def test_the_full_run_stops_when_most_notes_are_excluded(items, tmp_path):
    oracle = OracleLLM(items, fail_setting="*")
    with pytest.raises(TooManyExclusions, match="Stopping before more money is spent"):
        generate_llm(CFG, client(oracle, tmp_path), items)
    in_flight = CFG.llm.concurrency - 1  # notes already running when the guard trips still finish
    assert 50 * 3 <= len(oracle.calls) <= (50 + in_flight) * 3  # 50 notes x 3 attempts, then it stopped


def test_the_full_run_is_not_stopped_by_a_handful_of_exclusions(items, tmp_path):
    res = generate_llm(CFG, client(OracleLLM(items, fail_setting="shorthand", fail_every=20), tmp_path), items)
    assert res.tally.total_exclusion_rate() < 0.1 and res.by_split["train"]


# --- progress line ---------------------------------------------------------------------------------------------------------------

def test_progress_line_shows_counts_spend_and_eta():
    stream = io.StringIO()
    mock = MockClient(responder=lambda s, p: "x")
    c = CachedClient(mock, DiskCache("/nonexistent/never_written.jsonl"), Budget(10, 10.0, 0.1, 0.5), "1")
    c.misses, c.hits, c.budget.spend_usd = 24, 3, 0.0042
    pr = Progress("generate", c, stream)
    pr.started -= 60
    pr(setting="ehr_template", accepted=11, excluded=0, done=12, total=60)
    line = stream.getvalue().strip()
    assert line.startswith("generate [12/60] | ehr_template: 11 accepted")
    assert "calls 24 (cached 3)" in line and "$0.004" in line and "1m0" in line and "eta " in line


def test_progress_names_the_failures_when_notes_are_excluded():
    stream, tally = io.StringIO(), ExclusionTally()
    tally.failure_codes.update({"truncated": 9, "lab_missing": 2})
    Progress("pilot", None, stream)(setting="ehr_template", accepted=3, excluded=9, target=20, tally=tally)
    out = stream.getvalue()
    assert "ehr_template: 3/20 accepted, 9 excluded" in out and "failing on: truncated x9, lab_missing x2" in out


def test_progress_can_print_every_nth_note():
    stream = io.StringIO()
    pr = Progress("run", None, stream, every=3)
    for n in range(1, 10):
        pr(setting="s", accepted=n, excluded=0, done=n, total=9)
    assert len(stream.getvalue().strip().splitlines()) == 3


ARGS = ["--note-source", "llm", "--seed", "7", "--n-train", "400", "--n-test", "24", "--n-per-adversarial-type", "4"]


@pytest.fixture
def cfg_file(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"llm": {"matched_pairs": 6, "pilot_per_setting": 20}}))
    return ["--config", str(f)]


def test_pilot_command_prints_live_progress_by_default_and_not_when_quiet(monkeypatch, tmp_path, cfg_file, items, capsys):
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items))
    base = ["pilot", "--yes", "--cache", str(tmp_path / "c.jsonl"), *ARGS, *cfg_file]
    assert main([*base, "--out", str(tmp_path / "a")]) == 0
    err = capsys.readouterr().err
    assert re.search(r"pilot shorthand: \d+/20 accepted \| calls \d+ \(cached \d+\), \$\d\.\d{3} \|", err)
    assert main([*base, "--quiet", "--out", str(tmp_path / "b"), "--round", "0"]) == 0
    assert "accepted |" not in capsys.readouterr().err


def test_pilot_command_reports_an_aborted_setting(monkeypatch, tmp_path, cfg_file, items, capsys):
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items, fail_setting="ai_scribe"))
    assert main(["pilot", "--yes", "--cache", str(tmp_path / "c.jsonl"), "--out", str(tmp_path / "r"), *ARGS, *cfg_file]) == 0
    err = capsys.readouterr().err
    assert "ABORTED ai_scribe: 100% of its notes failed validation" in err and "stopped early" in err


def test_generate_command_stops_cleanly_on_runaway_exclusions(monkeypatch, tmp_path, cfg_file, items, capsys):
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items, fail_setting="*"))
    out = tmp_path / "out"
    code = main(["generate", "--yes", "--quiet", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *ARGS, *cfg_file])
    assert code == 3 and not out.exists()
    assert "Stopping before more money is spent" in capsys.readouterr().err


# --- logging -----------------------------------------------------------------------------------------------------------------------------

def test_every_paid_call_is_logged_with_tokens_stop_reason_and_duration(caplog, tmp_path):
    caplog.set_level(logging.INFO, logger="data_gen.llm")
    mock = MockClient(responder=lambda s, p: "ok", input_tokens=1200, output_tokens=540)
    c = client(mock, tmp_path)
    c.complete(system="s", prompt="p", model="m", max_tokens=100, nonce=2)
    c.complete(system="s", prompt="p", model="m", max_tokens=100, nonce=2)  # cached: not an API call
    lines = [r.getMessage() for r in caplog.records if "api call" in r.getMessage()]
    assert len(lines) == 1
    assert "writer nonce=2 in=1200 out=540 stop=end_turn" in lines[0] and re.search(r"\d+\.\ds", lines[0])


def test_cache_hits_are_logged_only_at_debug(caplog, tmp_path):
    c = client(MockClient(responder=lambda s, p: "ok"), tmp_path)
    c.complete(system="s", prompt="p", model="m", max_tokens=1)
    caplog.set_level(logging.INFO, logger="data_gen.llm")
    c.complete(system="s", prompt="p", model="m", max_tokens=1)
    assert not any("cache hit" in r.getMessage() for r in caplog.records)
    caplog.set_level(logging.DEBUG, logger="data_gen.llm")
    c.complete(system="s", prompt="p", model="m", max_tokens=1)
    assert any("cache hit" in r.getMessage() for r in caplog.records)


def test_slow_calls_and_truncated_responses_warn(caplog, tmp_path, monkeypatch):
    ticks = iter([0.0, 45.0, 100.0, 100.5])
    monkeypatch.setattr("data_gen.llm.gateway.time.monotonic", lambda: next(ticks))

    class Cut:
        def complete(self, **kw):
            return LLMResult("partial", 10, 700, "max_tokens")

    caplog.set_level(logging.WARNING, logger="data_gen.llm")
    c = CachedClient(Cut(), DiskCache(tmp_path / "w.jsonl"), Budget(10, 10.0, 0.1, 0.5), "1")
    c.complete(system="s", prompt="p", model="m", max_tokens=700)
    messages = [r.getMessage() for r in caplog.records]
    assert any("slow API call" in m and "45s" in m for m in messages)
    assert any("hit the output limit" in m and "700" in m for m in messages)


def test_attempt_failures_and_exclusions_are_logged(caplog):
    caplog.set_level(logging.INFO, logger="data_gen.llm")
    llm = Scripted([("", "max_tokens")] * 3)
    NoteWriter(llm, LLMConfig()).write(plan())
    messages = [r.getMessage() for r in caplog.records]
    assert sum("failed: truncated" in m for m in messages) == 3
    assert any("excluded after 3 attempts" in m for m in messages)


def test_verbose_flag_turns_on_info_logging(monkeypatch, tmp_path, capsys):
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    try:
        assert main(["estimate", "-v", "--cache", str(tmp_path / "c.jsonl"), *ARGS]) == 0
        assert root.level == logging.INFO
        assert main(["estimate", "-vv", "--cache", str(tmp_path / "c.jsonl"), *ARGS]) == 0
        assert root.level == logging.DEBUG
        assert main(["estimate", "--cache", str(tmp_path / "c.jsonl"), *ARGS]) == 0
        assert root.level == logging.WARNING
    finally:
        root.setLevel(before[0])
        root.handlers[:] = before[1]
    assert "estimated cost" in capsys.readouterr().out
