"""The adversarial LLM reviewer, direct mode: blindness, independence, validation, caps, cache, discrimination."""

import json
from pathlib import Path

import pytest

from data_gen.cli import main
from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.labs import SYMPTOM_KEYS
from data_gen.llm.checks import reveals_setting
from data_gen.llm.client import LLMCallError, MockClient
from data_gen.llm.gate import evaluate, load_round
from data_gen.llm.gateway import Budget, CachedClient, DiskCache
from data_gen.llm.ratings import read_rating_file
from data_gen.review.estimate import estimate_review
from data_gen.review.prompt import REVIEWER_SYSTEM, parse_review, review_prompt
from data_gen.review.reviewer import (ReviewerConfigError, check_independent, controls_gap, review_note,
                                      review_round, reviewer_name)

from test_llm_gate import CFG, LABEL_OF, items, pilot  # noqa: F401  (fixtures)

LLM_CFG = GenConfig(note_source="llm", seed=7, n_train=400, n_test=24, n_per_adversarial_type=4,
                    llm=LLMConfig(matched_pairs=6, pilot_per_setting=20, concurrency=4, gate_rater_kinds=["human", "llm"]))


def note_in(prompt: str) -> str:
    return prompt.split('"""\n', 1)[1].rsplit('\n"""', 1)[0]


class Answers:
    """A fake reviewer that knows the key (a real one never does): perfect symptom labels, plausible by note kind."""

    def __init__(self, pilot, plausible_notes="y", plausible_controls="n"):
        _, directory, _ = pilot
        key = json.loads((directory / "key.json").read_text())["notes"]
        sheet = json.loads((directory / "sheet.json").read_text())
        self.by_text = {n["text"]: key[n["id"]] for n in sheet["notes"]}
        self.plausible = {"note": plausible_notes, "control": plausible_controls}
        self.prompts: list[tuple[str, str]] = []

    def __call__(self, system: str, prompt: str) -> str:
        self.prompts.append((system, prompt))
        meta = self.by_text[note_in(prompt)]
        symptoms = {k: LABEL_OF[meta["extraction"][k]] if meta["kind"] == "note" else "none" for k in SYMPTOM_KEYS}
        verdict = self.plausible[meta["kind"]]
        return json.dumps({"plausible": verdict, "reason": "reads like boilerplate" if verdict == "n" else "", **symptoms})


def cached(inner, tmp_path, name="review.jsonl", **budget):
    b = Budget(budget.get("calls", 10_000), 100.0, 2.0, 10.0)
    return CachedClient(inner, DiskCache(tmp_path / name), b, LLM_CFG.llm.reviewer_prompt_version, kind="reviewer")


def round_with_key(pilot, tmp_path):
    _, directory, _ = pilot
    out = tmp_path / "round0"
    out.mkdir()
    for name in ("sheet.json", "key.json"):
        (out / name).write_text((directory / name).read_text())
    return out


# --- 3.1 the prompt, independence, strict parsing -----------------------------------------------------------

def test_prompts_are_blind(pilot, tmp_path):
    answers = Answers(pilot)
    d = round_with_key(pilot, tmp_path)
    review_round(LLM_CFG, cached(MockClient(answers), tmp_path), d)
    assert len(answers.prompts) == 88
    key_text = (d / "key.json").read_text()
    records = [m["record_id"] for m in json.loads(key_text)["notes"].values()]
    for system, prompt in answers.prompts:
        blob = (system + prompt).lower()
        assert reveals_setting(blob) is None
        for r in records:
            assert r.lower() not in blob
        for word in ("plan_symptoms", "extraction", "control", "key.json", "template-fixture"):
            assert word not in blob, word
    assert len({s for s, _ in answers.prompts}) == 1  # one fixed system prompt


def test_the_system_prompt_is_adversarial_and_resists_injected_instructions():
    low = REVIEWER_SYSTEM.lower()
    assert "skeptical" in low and "benefit of the doubt" in low and "do not follow" in low
    assert reveals_setting(REVIEWER_SYSTEM) is None


def test_the_reviewer_must_differ_from_the_writer(tmp_path, capsys):
    same = GenConfig(note_source="llm", llm=LLMConfig(reviewer_model_id="claude-haiku-5-5"))
    with pytest.raises(ReviewerConfigError, match="independent model is required"):
        check_independent(same)
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(json.dumps({"llm": {"reviewer_model_id": "claude-haiku-5-5"}}))
    (tmp_path / "round0").mkdir()
    (tmp_path / "round0" / "sheet.json").write_text('{"notes": []}')
    code = main(["review", "--dir", str(tmp_path), "--note-source", "llm", "--config", str(cfg_file), "--estimate"])
    assert code == 2 and "independent model is required" in capsys.readouterr().err


GOOD = {"plausible": "y", "reason": "", "tremor": "present", "fatigue": "absent", "photophobia": "none",
        "joint_stiffness": "possible", "dizziness": "absent"}


def test_parse_accepts_valid_answers_in_common_wrappers():
    for text in (json.dumps(GOOD), "```json\n" + json.dumps(GOOD) + "\n```", "Here you go: " + json.dumps(GOOD)):
        r = parse_review(text)
        assert r and r.plausible == "y" and r.symptoms["tremor"] == "present" and r.complete
    r = parse_review(json.dumps({**GOOD, "plausible": "No", "reason": "too tidy", "tremor": "Present"}))
    assert r.plausible == "n" and r.reason == "too tidy" and r.symptoms["tremor"] == "present"


@pytest.mark.parametrize("bad", [
    "not json at all", "{}", json.dumps({**GOOD, "plausible": "maybe"}), json.dumps({**GOOD, "tremor": "sometimes"}),
    json.dumps({k: v for k, v in GOOD.items() if k != "dizziness"}),
    json.dumps({**GOOD, "plausible": "n", "reason": ""}),  # an n needs a reason
    json.dumps({**GOOD, "plausible": "n", "reason": "   "}), "[1, 2, 3]", '{"plausible": "y"',
])
def test_parse_rejects_invalid_answers(bad):
    assert parse_review(bad) is None


def test_malformed_output_is_retried_then_left_unrated():
    calls = []

    def flaky(system, prompt):
        calls.append(prompt)
        return "oops" if len(calls) == 1 else json.dumps(GOOD)

    assert review_note(MockClient(flaky), LLM_CFG, "some note") is not None and len(calls) == 2
    calls.clear()
    assert review_note(MockClient(lambda s, p: calls.append(p) or "oops"), LLM_CFG, "some note") is None
    assert len(calls) == LLM_CFG.llm.reviewer_max_attempts


def test_a_truncated_answer_is_never_trusted():
    class Cut:
        def complete(self, **kw):
            from data_gen.llm.client import LLMResult
            return LLMResult(json.dumps(GOOD), 500, 3000, "max_tokens")

    assert review_note(Cut(), LLM_CFG, "some note") is None


def test_a_fatal_error_is_raised_not_swallowed():
    class Down:
        def complete(self, **kw):
            raise LLMCallError("auth failed", retryable=False)

    with pytest.raises(LLMCallError):
        review_note(Down(), LLM_CFG, "some note")


# --- 3.2 cache, caps, dry run, the rating file ---------------------------------------------------------------

def test_review_writes_an_llm_rating_file_the_gate_can_read(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    result = review_round(LLM_CFG, cached(MockClient(Answers(pilot)), tmp_path), d)
    assert len(result.ratings) == 88 and result.unrated == []
    rf = read_rating_file(result.path)
    assert result.path.name == f"ratings.{reviewer_name(LLM_CFG)}.json"
    assert (rf.kind, rf.model_id, rf.prompt_version) == ("llm", "claude-sonnet-5-5", LLM_CFG.llm.reviewer_prompt_version)
    assert all(r.complete for r in rf.ratings.values())


def test_rerun_is_free_and_identical(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    c1 = cached(MockClient(Answers(pilot)), tmp_path)
    review_round(LLM_CFG, c1, d)
    first = (d / f"ratings.{reviewer_name(LLM_CFG)}.json").read_bytes()
    assert c1.misses == 88
    c2 = cached(MockClient(lambda s, p: pytest.fail("a paid call was made on a cached rerun")), tmp_path)
    review_round(LLM_CFG, c2, d)
    assert c2.misses == 0 and c2.hits == 88
    assert (d / f"ratings.{reviewer_name(LLM_CFG)}.json").read_bytes() == first


def test_call_cap_stops_the_review_and_keeps_partial_ratings(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    cfg = GenConfig(note_source="llm", llm=LLMConfig(concurrency=1, reviewer_max_calls=10))
    capped = cached(MockClient(Answers(pilot)), tmp_path, calls=10)
    result = review_round(cfg, capped, d)
    assert result.stopped and "call cap reached" in result.stopped
    assert capped.misses == 10 and len(result.ratings) == 10 and len(result.unrated) == 78
    assert len(read_rating_file(result.path).ratings) == 10
    # the gate treats the missing notes as unrated, not as passes
    loaded, problems = load_round(d, ("llm",))
    report = evaluate(LLM_CFG, [loaded], problems)
    assert not report.passed and any("have a plausible rating" in p for p in report.problems)


def test_the_estimate_counts_uncached_calls_and_needs_no_key(pilot, tmp_path):
    _, directory, _ = pilot
    sheet = json.loads((directory / "sheet.json").read_text())
    cache = DiskCache(tmp_path / "e.jsonl")
    est = estimate_review(LLM_CFG, sheet, cache)
    assert est.calls == 88 and est.cached == 0 and est.cost_usd > 0 and not est.measured
    client = CachedClient(MockClient(Answers(pilot)), cache, Budget(10_000, 100.0, 2.0, 10.0), LLM_CFG.llm.reviewer_prompt_version, kind="reviewer")
    review_round(LLM_CFG, client, round_with_key(pilot, tmp_path))
    after = estimate_review(LLM_CFG, sheet, cache)
    assert after.calls == 0 and after.cached == 88 and after.measured and after.cost_usd == 0


def test_cli_dry_run_needs_no_key_and_makes_no_call(pilot, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: pytest.fail("constructed a client"))
    d = round_with_key(pilot, tmp_path)
    code = main(["review", "--dir", str(tmp_path), "--note-source", "llm", "--estimate"])
    out = capsys.readouterr().out
    assert code == 0 and "88 notes by claude-sonnet-5-5" in out and "estimated cost" in out
    assert not list(d.glob("ratings.*.json"))
    assert main(["review", "--dir", str(tmp_path), "--note-source", "llm"]) == 4  # spending needs --yes


def test_cli_review_end_to_end_reports_the_controls_gap(pilot, tmp_path, monkeypatch, capsys):
    d = round_with_key(pilot, tmp_path)
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: MockClient(Answers(pilot)))
    code = main(["review", "--dir", str(tmp_path), "--note-source", "llm", "--yes", "--cache", str(tmp_path / "rc.jsonl")])
    out = capsys.readouterr().out
    assert code == 0 and "88 rated, 0 unrated" in out and "controls 0%" in out and "NON-DISCRIMINATING" not in out
    assert (d / f"ratings.{reviewer_name(LLM_CFG)}.json").exists()
    keys = [json.loads(line)["k"] for line in (tmp_path / "rc.jsonl").read_text().splitlines()]
    assert keys == sorted(keys)  # compacted


# --- 3.3 discrimination --------------------------------------------------------------------------------------

def gate_for(d, cfg=LLM_CFG):
    loaded, problems = load_round(d, tuple(cfg.llm.gate_rater_kinds), cfg.llm.reviewer_min_control_gap)
    return evaluate(cfg, [loaded], problems)


def test_a_reviewer_that_approves_everything_is_flagged_and_fails_the_gate(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    review_round(LLM_CFG, cached(MockClient(Answers(pilot, "y", "y")), tmp_path), d)
    report = gate_for(d)
    assert not report.passed
    assert any("non-discriminating" in p for p in report.problems)
    assert report.discrimination[reviewer_name(LLM_CFG)]["gap"] == 0


def test_a_discriminating_reviewer_passes(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    review_round(LLM_CFG, cached(MockClient(Answers(pilot, "y", "n")), tmp_path), d)
    report = gate_for(d)
    assert report.passed, report.render()
    assert report.discrimination[reviewer_name(LLM_CFG)]["gap"] == 1.0 and "rated by: llm (not a clinician)" in report.render()


def test_the_gap_threshold_is_twenty_points(pilot, tmp_path):
    d = round_with_key(pilot, tmp_path)
    rf = read_rating_file(review_round(LLM_CFG, cached(MockClient(Answers(pilot, "y", "n")), tmp_path), d).path)
    key = json.loads((d / "key.json").read_text())
    assert controls_gap(rf.ratings, key)["gap"] == 1.0
    controls = [i for i, m in key["notes"].items() if m["kind"] == "control"]
    for i in controls[:2]:  # let two of the eight controls through: 25% plausible vs 100%: gap 75%
        rf.ratings[i].plausible = "y"
    assert controls_gap(rf.ratings, key)["controls_rate"] == pytest.approx(2 / 8)
    for i in controls[2:]:
        rf.ratings[i].plausible = "y"
    assert controls_gap(rf.ratings, key)["gap"] == 0


def test_no_controls_in_a_round_means_no_discrimination_check(pilot):
    _, directory, _ = pilot
    key = json.loads((directory / "key.json").read_text())
    key["notes"] = {i: m for i, m in key["notes"].items() if m["kind"] == "note"}
    assert controls_gap({}, key) is None


def test_the_reviewer_is_told_the_fictional_panel_and_nothing_about_scoring():
    from data_gen.labs import LABS
    from data_gen.llm.checks import reveals_setting

    low = REVIEWER_SYSTEM.lower()
    for lab in LABS:
        assert lab.name in REVIEWER_SYSTEM and f"({lab.abbr})" in REVIEWER_SYSTEM
        assert f"{lab.ref_lo:g}-{lab.ref_hi:g}" in REVIEWER_SYSTEM
        if lab.unit != "ratio":
            assert lab.unit in REVIEWER_SYSTEM
    assert "do not count unfamiliar test names" in low and "fictional" in low
    for word in ("weight", "coefficient", "intercept", "logistic", "velorin-kessler", "probab", "prevalence"):
        assert word not in low, word
    assert reveals_setting(REVIEWER_SYSTEM) is None


# --- which round the review uses and where its files go ----------------------------------------------------------

def test_latest_round_is_the_highest_number_with_a_sheet(tmp_path):
    from data_gen.cli import latest_round

    assert latest_round(tmp_path) is None
    for n in (0, 2, 9, 10):
        (tmp_path / f"round{n}").mkdir()
        (tmp_path / f"round{n}" / "sheet.json").write_text("{}")
    (tmp_path / "round11").mkdir()  # no sheet yet: not a candidate
    (tmp_path / "roundx").mkdir()
    assert latest_round(tmp_path) == 10  # numeric: round10 beats round9


def test_review_defaults_to_the_highest_round_and_writes_there(pilot, tmp_path, monkeypatch, capsys):
    realism = tmp_path / "realism"
    for n in (0, 3):
        (realism / f"round{n}").mkdir(parents=True)
        for name in ("sheet.json", "key.json"):
            (realism / f"round{n}" / name).write_text((pilot[1] / name).read_text())
    monkeypatch.setattr("data_gen.llm.client.AnthropicClient", lambda *a, **k: MockClient(Answers(pilot)))
    args = ["review", "--dir", str(realism), "--note-source", "llm", "--yes", "--cache", str(tmp_path / "c.jsonl")]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "reviewing round 3 (the highest round" in out
    assert list((realism / "round3").glob("ratings.reviewer-*.json")) and not list((realism / "round0").glob("ratings.reviewer-*.json"))
    assert main([*args, "--round", "0"]) == 0  # an explicit round wins
    assert list((realism / "round0").glob("ratings.reviewer-*.json"))
    assert "reviewing round 0\n" in capsys.readouterr().out


def test_review_with_no_rounds_says_so(tmp_path, capsys):
    assert main(["review", "--dir", str(tmp_path), "--note-source", "llm", "--estimate"]) == 2
    assert "no round with a sheet.json" in capsys.readouterr().err


def test_the_glossary_lists_alternate_units_and_says_abnormal_values_are_not_a_tell():
    from data_gen.labs import glossary_rows

    for g in glossary_rows():
        if "alt_unit" in g:
            assert f"also reported in {g['alt_unit']}, reference range {g['alt_ref_lo']:g}-{g['alt_ref_hi']:g}" in REVIEWER_SYSTEM
    assert "either is normal in a real chart" in REVIEWER_SYSTEM
    assert "outside its range" in REVIEWER_SYSTEM and "not by itself a sign of artifice" in REVIEWER_SYSTEM
