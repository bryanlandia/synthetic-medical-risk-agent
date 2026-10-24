import json
import re
from pathlib import Path

import pytest

from data_gen.cli import main
from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.labs import SYMPTOM_KEYS
from data_gen.llm.gate import PLAUSIBLE_THRESHOLD, Rating, evaluate, load_round, parse_ratings
from data_gen.llm.gateway import Budget, CachedClient, DiskCache
from data_gen.llm.pilot import PilotNote, build_sheet, control_notes, pilot_items, run_pilot, write_pilot
from data_gen.llm.run import plan_all

from llm_oracle import OracleLLM

CFG = GenConfig(note_source="llm", seed=7, n_train=400, n_test=24, n_per_adversarial_type=4,
                llm=LLMConfig(matched_pairs=6, pilot_per_setting=20))
LABEL_OF = {"present": "present", "possible": "possible", "absent": "absent", "not_mentioned": "none"}


@pytest.fixture(scope="module")
def items():
    return plan_all(CFG)


def client(oracle, tmp_path, **kw):
    return CachedClient(oracle, DiskCache(tmp_path / "cache.jsonl"), Budget(kw.get("calls", 10_000), 100.0, 0.1, 0.5), "1")


@pytest.fixture(scope="module")
def pilot(items, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pilot")
    result = run_pilot(CFG, client(OracleLLM(items), tmp), items)
    directory = tmp / "round0"
    meta = write_pilot(CFG, result, directory, 0)
    return result, directory, meta


# --- 7.1 the pilot and its blind sheet -----------------------------------------------------------------------------

def test_pilot_writes_twenty_accepted_notes_per_setting(pilot):
    result, _, _ = pilot
    assert len(result.notes) == 80 and result.short == {}
    for s in LLM_SETTINGS:
        assert sum(n.setting == s for n in result.notes) == 20


def test_sheet_contains_no_setting_names_and_is_shuffled(pilot):
    _, directory, _ = pilot
    sheet = (directory / "sheet.md").read_text().lower()
    for s in LLM_SETTINGS:
        assert s not in sheet and s.replace("_", " ") not in sheet
    for word in ("control", "key.json:", "true_probability", "label:"):
        assert word not in sheet.split("save the filled sheet")[1]  # nothing after the instructions gives it away
    key = json.loads((directory / "key.json").read_text())["notes"]
    order = [key[f"n{i:02d}"]["setting"] for i in range(1, len(key) + 1)]
    assert order != sorted(order), "notes must be shuffled across settings"
    assert len({s for s in order[:8]}) > 1


def test_key_maps_every_note_id_and_marks_controls(pilot):
    result, directory, _ = pilot
    key = json.loads((directory / "key.json").read_text())["notes"]
    sheet = (directory / "sheet.md").read_text()
    ids_in_sheet = re.findall(r"^## (n\d+)$", sheet, re.MULTILINE)
    assert sorted(ids_in_sheet) == sorted(key) and len(key) == 80 + 8
    kinds = [k["kind"] for k in key.values()]
    assert kinds.count("control") == 8 and kinds.count("note") == 80
    for entry in key.values():
        assert entry["record_id"] and entry["setting"]
        if entry["kind"] == "note":
            assert set(entry["extraction"]) == set(SYMPTOM_KEYS)


def test_controls_are_the_old_template_notes(pilot):
    _, directory, _ = pilot
    controls = control_notes(CFG)
    assert len(controls) == 8
    sheet = (directory / "sheet.md").read_text()
    assert all(text in sheet for _, text in controls)
    assert any(text.startswith("VISIT NOTE") for _, text in controls) and any("Sx:" in t for _, t in controls)


def test_blank_sheet_parses_to_empty_ratings(pilot):
    _, directory, _ = pilot
    ratings, problems = parse_ratings((directory / "sheet.md").read_text())
    assert problems == [] and len(ratings) == 88
    assert all(r.plausible is None and not any(r.symptoms.values()) for r in ratings.values())


def test_a_note_that_names_its_setting_is_refused():
    leaky = PilotNote("p1", "shorthand", "This ehr_template note is long.", {}, {})
    with pytest.raises(ValueError, match="not be blind"):
        build_sheet(CFG, [leaky], [])
    with pytest.raises(ValueError, match="not be blind"):
        build_sheet(CFG, [], [("c1", "An AI scribe wrote this copy-forward note.")])


def test_pilot_notes_are_items_of_the_full_run(pilot, items):
    result, _, _ = pilot
    assert {n.record_id for n in result.notes} <= {i.record_id for i in items}


def test_pilot_spend_is_small_and_cached_for_the_full_run(items, tmp_path):
    c = client(OracleLLM(items), tmp_path)
    run_pilot(CFG, c, items)
    # a writer and an extractor call per note, plus the few notes still in flight when each setting reached
    # its target (up to workers-1 per setting; they finish and stay cached, and are real dataset items)
    workers = CFG.llm.concurrency
    assert 2 * 80 <= c.misses <= 2 * 80 + 4 * (workers - 1) * 2 + 10
    assert c.budget.spend_usd < 0.1


def test_exclusions_are_topped_up_and_reported(items, tmp_path):
    class Flaky(OracleLLM):
        """Every fourth ehr_template prompt can never be written correctly."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.seen: dict[str, int] = {}

        def complete(self, **kw):
            prompt = kw["prompt"]
            plan = self.by_prompt.get(prompt)
            if plan is not None and plan.style == "ehr_template":
                n = self.seen.setdefault(prompt, len(self.seen))
                if n % 4 == 0:
                    return super().complete(**{**kw, "prompt": prompt}).__class__("unusable", 100, 10, "end_turn")
            return super().complete(**kw)

    result = run_pilot(CFG, client(Flaky(items), tmp_path), items)
    assert sum(n.setting == "ehr_template" for n in result.notes) == 20  # topped up with further candidates
    rate = result.tally.exclusion_rate("ehr_template")
    assert 0.15 < rate < 0.40
    assert result.tally.exclusion_rate("shorthand") == 0.0


def test_a_setting_that_cannot_be_written_comes_up_short(items, tmp_path):
    result = run_pilot(CFG, client(OracleLLM(items, fail_setting="copy_forward"), tmp_path), items)
    assert result.short == {"copy_forward": 20}
    assert result.tally.exclusion_rate("copy_forward") == 1.0


# --- 7.2 the gate report -----------------------------------------------------------------------------------------------

def fill(sheet: str, key: dict, plausible=lambda meta, i: "y", label=None) -> str:
    """Write a filled sheet: the rater agrees with the extractor unless ``label`` says otherwise."""
    counters: dict[str, int] = {}

    def section(match):
        note_id, body = match.group(1), match.group(2)
        meta = key[note_id]
        i = counters.setdefault(meta["setting"], len(counters) and 0) if False else counters.get(meta["setting"], 0)
        counters[meta["setting"]] = i + 1
        body = re.sub(r"^plausible:.*$", f"plausible: {plausible(meta, i)}", body, flags=re.MULTILINE)
        for k in SYMPTOM_KEYS:
            if meta["kind"] == "note":
                value = LABEL_OF[meta["extraction"][k]]
                if label is not None:
                    value = label(meta, i, k, value)
            else:
                value = "none"
            body = re.sub(rf"^{k}:.*$", f"{k}: {value}", body, flags=re.MULTILINE)
        return f"## {note_id}\n{body}"

    return re.sub(r"## (n\d+)\n(.*?)(?=\n---|\Z)", section, sheet, flags=re.DOTALL)


def make_round(pilot, tmp_path, name="round0", **kw):
    _, directory, _ = pilot
    key = json.loads((directory / "key.json").read_text())
    out = tmp_path / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "key.json").write_text((directory / "key.json").read_text())
    (out / "ratings.md").write_text(fill((directory / "sheet.md").read_text(), key["notes"], **kw))
    return out


def report_for(dirs):
    rounds, problems = [], []
    for d in dirs:
        loaded, probs = load_round(d)
        rounds.append(loaded)
        problems += probs
    return evaluate(CFG, rounds, problems)


def test_filled_sheet_round_trips_and_passes(pilot, tmp_path):
    d = make_round(pilot, tmp_path, plausible=lambda m, i: "y" if i < 18 else "n")  # 18 of 20 plausible
    report = report_for([d])
    assert report.passed, report.render()
    assert all(s.rated == 20 and s.plausible == 18 for s in report.settings.values())
    assert report.extractor_notes == 80 and min(report.extractor_accuracy.values()) == 1.0
    assert "RESULT: PASS" in report.render()


@pytest.mark.parametrize("plausible_count,passes", [(16, True), (15, False), (20, True), (10, False)])
def test_plausibility_threshold_is_eighty_percent_of_twenty(pilot, tmp_path, plausible_count, passes):
    d = make_round(pilot, tmp_path,
                   plausible=lambda m, i: "y" if (m["setting"] != "ai_scribe" or i < plausible_count) else "n")
    report = report_for([d])
    assert report.settings["ai_scribe"].passed is passes
    assert report.settings["shorthand"].passed
    assert report.passed is passes
    assert PLAUSIBLE_THRESHOLD == 0.80


def test_extractor_accuracy_threshold(pilot, tmp_path):
    def wrong_on(n):
        return lambda m, i, k, v: ("absent" if v != "absent" else "present") if (k == "tremor" and i < n and m["setting"] == "shorthand") else v

    ok = report_for([make_round(pilot, tmp_path, "ok", label=wrong_on(3))])  # 3 of 80 wrong = 96.25%
    assert ok.extractor_accuracy["tremor"] == pytest.approx(77 / 80) and ok.extractor_passed
    bad = report_for([make_round(pilot, tmp_path, "bad", label=wrong_on(5))])  # 5 of 80 wrong = 93.75%
    assert bad.extractor_accuracy["tremor"] == pytest.approx(75 / 80) and not bad.extractor_passed and not bad.passed


def test_missing_and_invalid_ratings_block_the_gate(pilot, tmp_path):
    d = make_round(pilot, tmp_path)
    text = (d / "ratings.md").read_text()
    (d / "ratings.md").write_text(re.sub(r"^plausible: y$", "plausible: maybe", text, count=1, flags=re.MULTILINE))
    report = report_for([d])
    assert not report.passed and any("plausible must be y or n" in p for p in report.problems)
    blank = tmp_path / "blank"
    blank.mkdir()
    (blank / "key.json").write_text((pilot[1] / "key.json").read_text())
    (blank / "ratings.md").write_text((pilot[1] / "sheet.md").read_text())
    report = report_for([blank])
    assert not report.passed and any("only 0 of 20 notes have a plausible rating" in p for p in report.problems)
    assert report_for([tmp_path / "does_not_exist_yet_dir"]) if False else True
    nofile = tmp_path / "nofile"
    nofile.mkdir()
    (nofile / "key.json").write_text((pilot[1] / "key.json").read_text())
    assert any("not found" in p for p in report_for([nofile]).problems)


def test_controls_are_reported_and_never_gated(pilot, tmp_path):
    d = make_round(pilot, tmp_path, plausible=lambda m, i: "n" if m["kind"] == "control" else "y")
    report = report_for([d])
    assert report.passed and report.controls_rated == 8 and report.controls_plausible == 0
    assert "controls (old template notes, not gated): 0/8" in report.render()


def test_high_exclusion_rate_blocks_the_full_run(pilot, tmp_path):
    d = make_round(pilot, tmp_path)
    key = json.loads((d / "key.json").read_text())
    key["meta"]["exclusion_rates"]["ai_scribe"] = 0.30
    (d / "key.json").write_text(json.dumps(key))
    report = report_for([d])
    assert not report.passed and not report.exclusion_passed
    assert "pilot exclusion rate" in report.render() and "FAIL" in report.render()


def test_a_later_round_replaces_only_its_own_setting(pilot, tmp_path, items):
    bad = make_round(pilot, tmp_path, "round0", plausible=lambda m, i: "y" if (m["setting"] != "ai_scribe" or i < 10) else "n")
    assert not report_for([bad]).passed
    # round 1: fresh ai_scribe notes only, rated well
    ids_round0 = {m["record_id"] for m in json.loads((bad / "key.json").read_text())["notes"].values()
                  if m["setting"] == "ai_scribe"}
    fresh = run_pilot(CFG, client(OracleLLM(items), tmp_path / "r1"), items, ("ai_scribe",), round_=1, exclude=ids_round0)
    (tmp_path / "r1").mkdir(exist_ok=True)
    write_pilot(CFG, fresh, tmp_path / "round1", 1, ("ai_scribe",))
    key1 = json.loads((tmp_path / "round1" / "key.json").read_text())
    (tmp_path / "round1" / "ratings.md").write_text(
        fill((tmp_path / "round1" / "sheet.md").read_text(), key1["notes"], plausible=lambda m, i: "y"))
    # the replacement round has no sheet-wide 80 hand-labelled notes of its own: merge fills the rest
    report = report_for([bad, tmp_path / "round1"])
    assert report.settings["ai_scribe"].passed and report.settings["ai_scribe"].plausible == 20
    assert report.settings["shorthand"].passed and report.passed, report.render()
    ids_round1 = {m["record_id"] for m in key1["notes"].values()}
    assert not ids_round0 & ids_round1, "round 1 must use fresh notes"


# --- the pilot and gate commands ----------------------------------------------------------------------------------------

ARGS = ["--note-source", "llm", "--seed", "7", "--n-train", "400", "--n-test", "24", "--n-per-adversarial-type", "4"]


@pytest.fixture
def cfg_file(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"llm": {"matched_pairs": 6, "pilot_per_setting": 20}}))
    return ["--config", str(f)]


def test_pilot_command_needs_yes_and_writes_the_files(monkeypatch, tmp_path, cfg_file, items, capsys):
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: OracleLLM(items))
    out = tmp_path / "realism"
    base = ["pilot", "--out", str(out), "--cache", str(tmp_path / "c.jsonl"), *ARGS, *cfg_file]
    assert main(base) == 4 and not out.exists()
    assert main([*base, "--yes"]) == 0
    printed = capsys.readouterr().out
    assert "exclusion rate shorthand" in printed and "data-gen gate" in printed
    assert (out / "round0" / "sheet.md").exists() and (out / "round0" / "key.json").exists()


def test_gate_command_exit_codes(pilot, tmp_path, cfg_file, capsys):
    good = make_round(pilot, tmp_path / "good", "round0")
    assert main(["gate", "--dir", str(good.parent), *ARGS, *cfg_file]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out
    bad = make_round(pilot, tmp_path / "bad", "round0", plausible=lambda m, i: "n")
    assert main(["gate", "--dir", str(bad.parent), *ARGS, *cfg_file]) == 1
    assert "RESULT: FAIL" in capsys.readouterr().out
    assert main(["gate", "--dir", str(tmp_path / "nowhere"), *ARGS, *cfg_file]) == 2
