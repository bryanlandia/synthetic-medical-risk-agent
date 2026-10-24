"""Rating files, the machine-readable blind sheet, and a gate that counts only the configured rater kinds."""

import json
import re

import pytest
from pydantic import ValidationError

from data_gen.cli import main
from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.labs import SYMPTOM_KEYS
from data_gen.llm.gate import evaluate, load_gate_result, load_round
from data_gen.llm.ratings import (NoteRating, RatingFile, rater_slug, rating_files, rating_path, read_rating_file,
                                  write_rating_file)

from test_llm_gate import CFG, LABEL_OF, items, make_round, pilot  # noqa: F401  (fixtures)


def blind(directory):
    return json.loads((directory / "sheet.json").read_text())


def perfect_file(pilot, kind="human", rater="Dr. Reyes", plausible=lambda meta, i: "y", **extra):
    """A rating file that labels every note exactly as the extractor read it."""
    _, directory, _ = pilot
    key = json.loads((directory / "key.json").read_text())["notes"]
    seen: dict[str, int] = {}
    ratings = {}
    for note_id, meta in key.items():
        i = seen[meta["setting"]] = seen.get(meta["setting"], -1) + 1
        symptoms = {k: LABEL_OF[meta["extraction"][k]] if meta["kind"] == "note" else "none" for k in SYMPTOM_KEYS}
        ratings[note_id] = NoteRating(plausible=plausible(meta, i), symptoms=symptoms)
    if kind == "llm":
        extra = {"model_id": "claude-sonnet-5-5", "prompt_version": "1", **extra}
    return RatingFile(rater=rater, kind=kind, ratings=ratings, **extra)


def round_dir(pilot, tmp_path, *files, name="round0"):
    _, directory, _ = pilot
    out = tmp_path / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "key.json").write_text((directory / "key.json").read_text())
    for f in files:
        write_rating_file(out, f)
    return out


def report_for(d, kinds=("human",), cfg=CFG):
    loaded, problems = load_round(d, kinds)
    return evaluate(cfg, [loaded], problems)


# --- 1.1 the blind sheet.json ----------------------------------------------------------------------------------

def test_blind_sheet_has_no_setting_names_plans_or_key_contents(pilot):
    _, directory, _ = pilot
    text = (directory / "sheet.json").read_text().lower()
    for s in LLM_SETTINGS:
        assert s not in text and s.replace("_", " ") not in text
    key = json.loads((directory / "key.json").read_text())["notes"]
    for meta in key.values():
        assert meta["record_id"].lower() not in text
    for field in ("plan_symptoms", "extraction", '"setting"', '"kind"', "control"):
        assert field not in text
    assert set(blind(directory)) == {"version", "notice", "symptom_keys", "plausible_values", "symptom_values", "notes"}


def test_blind_sheet_lists_the_same_notes_as_the_markdown_sheet(pilot):
    _, directory, _ = pilot
    md = (directory / "sheet.md").read_text()
    from_md = re.findall(r"^## (n\d+)\n\n```\n(.*?)\n```", md, re.MULTILINE | re.DOTALL)
    from_json = [(n["id"], n["text"]) for n in blind(directory)["notes"]]
    assert from_md == from_json and len(from_json) == 88


# --- 1.2 rating files ---------------------------------------------------------------------------------------------------

def test_rating_file_round_trips_and_leaves_no_temp_file(tmp_path):
    rf = RatingFile(rater="Dr. A. Reyes", kind="human", ratings={
        "n01": NoteRating(plausible="y", symptoms={k: "none" for k in SYMPTOM_KEYS}, comment="fine")})
    path = write_rating_file(tmp_path, rf)
    assert path == rating_path(tmp_path, "Dr. A. Reyes") and path.name == "ratings.dr.-a.-reyes.json"
    assert read_rating_file(path) == rf
    assert rating_files(tmp_path) == [path] and not list(tmp_path.glob("*.tmp"))
    write_rating_file(tmp_path, rf)  # overwriting is fine
    assert len(rating_files(tmp_path)) == 1


@pytest.mark.parametrize("bad", [
    dict(plausible="maybe"),
    dict(symptoms={"tremor": "sometimes"}),
    dict(symptoms={"unknown_symptom": "present"}),
])
def test_invalid_values_are_rejected(bad):
    with pytest.raises(ValidationError):
        NoteRating(**bad)


def test_rater_kind_and_provenance_rules():
    with pytest.raises(ValidationError):
        RatingFile(rater="reviewer", kind="llm")  # an llm file must say which model and prompt
    with pytest.raises(ValidationError):
        RatingFile(rater="Dr A", kind="human", model_id="claude-sonnet-5-5")
    with pytest.raises(ValidationError):
        RatingFile(rater="x", kind="robot")
    ok = RatingFile(rater="rev", kind="llm", model_id="claude-sonnet-5-5", prompt_version="1")
    assert ok.model_id == "claude-sonnet-5-5"


def test_rater_names_become_safe_file_names():
    assert rater_slug("Dr. Reyes / ../etc") == "dr.-reyes-..-etc"
    assert "/" not in rater_slug("../../x") and not rater_slug("../../x").startswith(".")
    with pytest.raises(ValueError):
        rater_slug("///")


# --- 1.3 the gate and rater kinds ------------------------------------------------------------------------------------

def test_a_human_rating_file_passes_the_gate(pilot, tmp_path):
    d = round_dir(pilot, tmp_path, perfect_file(pilot))
    report = report_for(d)
    assert report.passed, report.render()
    assert report.raters == ["human"] and "rated by: human" in report.render()


def test_llm_ratings_alone_do_not_pass_by_default(pilot, tmp_path):
    d = round_dir(pilot, tmp_path, perfect_file(pilot, kind="llm", rater="sonnet"))
    report = report_for(d)  # default accepted kinds: human only
    assert not report.passed
    assert any("no ratings from an accepted rater kind" in p and "llm" in p for p in report.problems)


def test_llm_ratings_can_be_accepted_explicitly(pilot, tmp_path):
    d = round_dir(pilot, tmp_path, perfect_file(pilot, kind="llm", rater="sonnet"))
    report = report_for(d, kinds=("human", "llm"))
    assert report.passed, report.render()
    assert report.raters == ["llm"] and "rated by: llm (not a clinician)" in report.render()


def test_hand_filled_markdown_still_counts_as_human(pilot, tmp_path):
    d = make_round(pilot, tmp_path)
    report = report_for(d)
    assert report.passed and report.raters == ["human"]


def test_disagreement_counts_as_implausible_and_is_reported(pilot, tmp_path):
    human = perfect_file(pilot)  # says y to everything
    llm = perfect_file(pilot, kind="llm", rater="sonnet", plausible=lambda m, i: "n" if i < 5 else "y")
    d = round_dir(pilot, tmp_path, human, llm)
    report = report_for(d, kinds=("human", "llm"))
    assert all(s.rated == 20 and s.plausible == 15 for s in report.settings.values())  # 5 of 20 pulled down
    assert not report.passed
    assert all(v == 5 for v in report.disagreements.values())
    assert "disagreed on plausibility" in report.render()
    assert set(report.raters) == {"human", "llm"}


def test_an_unaccepted_kind_is_ignored_even_when_present(pilot, tmp_path):
    human = perfect_file(pilot)
    llm = perfect_file(pilot, kind="llm", rater="sonnet", plausible=lambda m, i: "n")
    d = round_dir(pilot, tmp_path, human, llm)
    report = report_for(d)  # human only
    assert report.passed and report.raters == ["human"] and not any(report.disagreements.values())


def test_invalid_rating_file_blocks_the_gate(pilot, tmp_path):
    d = round_dir(pilot, tmp_path, perfect_file(pilot))
    (d / "ratings.broken.json").write_text('{"rater": "x", "kind": "human", "ratings": {"n01": {"plausible": "maybe"}}}')
    report = report_for(d)
    assert not report.passed and any("ratings.broken.json" in p for p in report.problems)


def test_the_default_accepted_kind_is_human_and_is_not_part_of_the_data_hash():
    assert LLMConfig().gate_rater_kinds == ["human"]
    a = GenConfig(note_source="llm", llm=LLMConfig())
    b = GenConfig(note_source="llm", llm=LLMConfig(gate_rater_kinds=["human", "llm"]))
    assert a.config_hash() == b.config_hash() and "gate_rater_kinds" not in b.canonical_dump().get("llm", {})
    with pytest.raises(ValidationError):
        LLMConfig(gate_rater_kinds=[])
    with pytest.raises(ValidationError):
        LLMConfig(gate_rater_kinds=["robot"])


# --- 1.4 the gate result reaches the manifest and README ---------------------------------------------------------------

def run_gate_cli(pilot, tmp_path, files, config=None):
    realism = tmp_path / "realism"
    d = round_dir(pilot, realism, *files)
    args = ["gate", "--dir", str(realism), "--note-source", "llm", "--seed", "7", "--n-train", "400", "--n-test", "24",
            "--n-per-adversarial-type", "4"]
    if config:
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(json.dumps(config))
        args += ["--config", str(cfg_file)]
    return main(args), realism, d


def test_gate_command_saves_who_rated(pilot, tmp_path, capsys):
    code, realism, _ = run_gate_cli(pilot, tmp_path, [perfect_file(pilot, kind="llm", rater="sonnet")],
                                    {"llm": {"pilot_per_setting": 20, "matched_pairs": 6,
                                             "gate_rater_kinds": ["human", "llm"]}})
    assert code == 0 and "rated by: llm (not a clinician)" in capsys.readouterr().out
    saved = load_gate_result(realism)
    assert saved["passed"] and saved["rater_kinds"] == ["llm"] and saved["description"] == "an LLM review, not a clinician"


def test_failed_gate_for_missing_kind_exits_nonzero(pilot, tmp_path):
    code, realism, _ = run_gate_cli(pilot, tmp_path, [perfect_file(pilot, kind="llm", rater="sonnet")],
                                    {"llm": {"pilot_per_setting": 20, "matched_pairs": 6}})
    assert code == 1 and load_gate_result(realism)["passed"] is False


def test_manifest_and_readme_say_the_review_was_by_an_llm(items, pilot, tmp_path):
    from data_gen.llm.gateway import Budget, CachedClient, DiskCache
    from data_gen.llm.run import run_and_write
    from llm_oracle import OracleLLM

    review = {"passed": True, "rater_kinds": ["llm"], "raters": ["sonnet"],
              "description": "an LLM review, not a clinician", "disagreements": {}}
    client = CachedClient(OracleLLM(items), DiskCache(tmp_path / "c.jsonl"), Budget(10**6, 100.0, 0.1, 0.5), "1")
    run_and_write(CFG, client, tmp_path / "out", items, realism_review=review)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["llm"]["realism_review"]["rater_kinds"] == ["llm"]
    readme = (tmp_path / "out" / "README.md").read_text()
    assert "reviewed by an LLM review, not a clinician" in readme and "not a clinical validation" in readme
    assert "FICTIONAL" in readme.upper() or "synthetic" in readme.lower()


def test_template_datasets_are_unchanged_by_any_of_this(tmp_path):
    from data_gen.dataset_io import write_dataset
    from data_gen.builder import build_dataset

    cfg = GenConfig(n_train=60, n_test=20, n_per_adversarial_type=3)
    manifest = write_dataset(build_dataset(cfg), cfg, tmp_path)
    assert "llm" not in manifest and not (tmp_path / "README.md").exists()


# --- the rating app (TypeScript) and this module must agree ---------------------------------------------------------

def test_rater_slugs_agree_with_the_rating_app():
    from pathlib import Path

    cases = json.loads((Path(__file__).parents[2] / "rating_ui" / "tests" / "slug-cases.json").read_text())
    for name, slug in cases:
        if slug is None:
            with pytest.raises(ValueError):
                rater_slug(name)
        else:
            assert rater_slug(name) == slug, name


def test_a_file_in_the_shape_the_app_writes_is_read_by_the_gate_side(tmp_path):
    app_output = {
        "kind": "human", "model_id": None, "prompt_version": None, "rater": "Dr. Reyes", "version": 1,
        "ratings": {"n01": {"comment": "", "plausible": "y", "reason": "",
                            "symptoms": {"dizziness": "none", "fatigue": "possible", "joint_stiffness": "absent",
                                         "photophobia": "present", "tremor": "present"}},
                    "n02": {"comment": "template residue", "plausible": "n", "reason": "", "symptoms": {}}},
    }
    path = tmp_path / "ratings.dr.-reyes.json"
    path.write_text(json.dumps(app_output))
    rf = read_rating_file(path)
    assert rf.kind == "human" and rf.ratings["n01"].complete and not rf.ratings["n02"].complete
