import json

import pytest
from data_gen.llm.client import MockClient

from evals import frontier_cli, protocol
from evals.baseline_report import FINAL_STAGES, check_reading, failed_graders, failing_ids, final_runs, generate
from evals.cli import build_parser
from evals.frontier import FINAL_MODEL, load_prompt
from evals.prompt_system import prompt_hash
from evals.systems import scored_report


def parse(*argv):
    return build_parser().parse_args(list(argv))


@pytest.fixture(scope="module")
def finished(dataset, tmp_path_factory):
    """A small end-to-end baseline with a scripted model that always says 0.3: iterate, freeze, three final stages."""
    tmp = tmp_path_factory.mktemp("baseline")
    client = MockClient(responder=lambda s, p: json.dumps(scored_report(json.loads(p), 0.3, uncertain=False)),
                        input_tokens=1800, output_tokens=600)
    mp = pytest.MonkeyPatch()
    mp.setattr(frontier_cli, "make_client", lambda: client)
    mp.setenv("ANTHROPIC_API_KEY", "k")
    paths = dict(protocol_path=tmp / "pv.json", out_root=tmp / "out", cache=tmp / "cache.jsonl")
    ledger = tmp / "ledger.json"
    assert frontier_cli.cmd_iterate(parse("iterate", "--prompt", "v1", "--yes", "--note", "first"), dataset, **paths) == 0
    assert frontier_cli.cmd_freeze(parse("freeze", "--prompt", "v1"), paths["protocol_path"]) == 0
    run = lambda *a: frontier_cli.cmd_run(parse("run", "--system", "frontier", "--model", "sonnet", "--final", "--yes", *a), dataset,  # noqa: E731
                                          ledger_path=ledger, **paths)
    assert run("--split", "test", "--limit", "40") == 0
    assert run("--split", "adversarial", "--limit", "40") == 0
    assert run("--split", "test", "--suites", "consistency", "--trials", "3", "--limit", "15") == 0
    mp.undo()
    return paths


def test_the_final_stages_are_found_and_their_graders_that_missed_a_target_are_listed(finished):
    runs = final_runs(finished["out_root"], FINAL_MODEL)
    assert set(runs) == set(FINAL_STAGES)
    failed = failed_graders(runs)
    assert {"happy_path", "symptom_reading", "data_quality", "borderline"} <= set(failed)
    assert "safety" not in failed and "parse" not in failed  # the scripted model always returns a valid, safe report


def test_the_report_is_incomplete_until_every_failed_grader_has_been_read(finished):
    text, missing = generate(finished["out_root"], protocol_path=finished["protocol_path"])
    assert text.startswith("# Frontier baseline") and "**INCOMPLETE.**" in text
    assert any(m.startswith("happy_path: no entry") for m in missing) and not any("final stage" in m for m in missing)


def reading_for(runs, findings="The scripted model ignores the record.", only=None):
    rows = [r for run in runs.values() for r in run["rows"]]
    out = []
    for grader in failed_graders(runs):
        ids = sorted(failing_ids(rows, grader))
        out.append({"grader": grader, "transcripts": ids[:10], "findings": findings, "grader_fault": None})
    return {"readings": [e for e in out if only is None or e["grader"] in only]}


def test_a_reading_that_covers_every_failed_grader_completes_the_report(finished):
    runs = final_runs(finished["out_root"], FINAL_MODEL)
    path = finished["out_root"] / "reading.json"
    path.write_text(json.dumps(reading_for(runs)))
    text, missing = generate(finished["out_root"], reading_path=path, protocol_path=finished["protocol_path"])
    assert missing == [] and "INCOMPLETE" not in text
    frozen = protocol.frozen(finished["protocol_path"])["prompt_hash"]
    assert frozen == prompt_hash(load_prompt("v1")) and frozen in text and FINAL_MODEL in text
    for heading in ("## Dev: v1_claude-haiku-5-5", "## Test (one final run)", "## Adversarial (one final run)",
                    "## Matched pairs, three trials", "## Prompt versions scored on dev", "## What was read"):
        assert heading in text
    assert "| happy_path | auc |" in text and "MDD" in text and "Against target" in text and "Total spend" in text


def test_a_reading_cannot_claim_transcripts_that_did_not_fail_or_were_not_enough(finished):
    runs = final_runs(finished["out_root"], FINAL_MODEL)
    good = reading_for(runs)
    bogus = json.loads(json.dumps(good))
    bogus["readings"][0]["transcripts"] = ["happy_path:no-such-patient:0"]
    assert any("not failing transcripts" in p for p in check_reading(runs, bogus))
    few = json.loads(json.dumps(good))
    few["readings"][0]["transcripts"] = few["readings"][0]["transcripts"][:3]
    assert any("read 3 of the" in p for p in check_reading(runs, few))
    blank = json.loads(json.dumps(good))
    blank["readings"][0]["findings"] = "  "
    assert any("no findings" in p for p in check_reading(runs, blank))
    assert check_reading(runs, good) == []


def test_fewer_than_ten_failures_need_all_of_them_read(finished):
    runs = final_runs(finished["out_root"], FINAL_MODEL)
    rows = [r for run in runs.values() for r in run["rows"]]
    small = {g: failing_ids(rows, g) for g in failed_graders(runs)}
    grader, ids = min(small.items(), key=lambda kv: len(kv[1]))
    if len(ids) >= 10:
        pytest.skip("every failed grader has at least ten failing transcripts in this fixture")
    reading = reading_for(runs)
    entry = next(e for e in reading["readings"] if e["grader"] == grader)
    assert len(entry["transcripts"]) == len(ids) and check_reading(runs, reading) == []


def test_the_report_command_writes_the_file_and_signals_incompleteness(finished):
    out = finished["out_root"]
    (out / "reading.json").unlink(missing_ok=True)
    assert frontier_cli.cmd_report(parse("report", "--model", "sonnet"), root=out, protocol_path=finished["protocol_path"]) == 1
    assert (out / "report.md").exists()
    (out / "reading.json").write_text(json.dumps(reading_for(final_runs(out, FINAL_MODEL))))
    assert frontier_cli.cmd_report(parse("report", "--model", "sonnet"), root=out, protocol_path=finished["protocol_path"]) == 0


def test_with_three_failures_all_three_must_be_read():
    rows = [{"suite": "happy_path", "sample_id": f"p{i}", "trial_index": 0, "graders": {"parse": {"passed": False}}}
            for i in range(3)]
    runs = {"test": {"summary": {"rows": [{"category": "parse", "metric": "failure_rate", "reached": False}]},
                     "rows": rows}}
    ids = [f"happy_path:p{i}:0" for i in range(3)]
    entry = lambda t: {"readings": [{"grader": "parse", "transcripts": t, "findings": "malformed"}]}  # noqa: E731
    assert check_reading(runs, entry(ids)) == []
    assert any("read 2 of the 3" in p for p in check_reading(runs, entry(ids[:2])))
