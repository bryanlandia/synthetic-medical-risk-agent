import json
import shutil
from pathlib import Path

from training import report_cmd

RESULTS = report_cmd.RESULTS_ROOT


def test_the_committed_report_is_complete():
    text, missing = report_cmd.generate()
    assert missing == [] and "INCOMPLETE" not in text
    assert "676 of 676 matched-pair records gave the identical report" in text
    assert "## test" in text and "## adversarial" in text and "## trials" in text and "frontier baseline" in text


def test_without_the_reading_the_report_is_incomplete_and_names_what_is_missing(tmp_path):
    text, missing = report_cmd.generate(reading_path=tmp_path / "none.json")
    assert text.startswith("# Classifier") and "INCOMPLETE" in text
    assert any(m.startswith("happy_path: no entry in the reading file") for m in missing)


def test_a_reading_that_names_transcripts_that_did_not_fail_is_rejected(tmp_path):
    reading = json.loads((report_cmd.READING).read_text())
    reading["readings"][0]["transcripts"] = ["happy_path:P20261-000001:0"] * 12
    path = tmp_path / "reading.json"
    path.write_text(json.dumps(reading))
    _, missing = report_cmd.generate(reading_path=path)
    assert any("are not failing transcripts" in m for m in missing)


def test_a_reading_with_fewer_than_ten_transcripts_is_rejected(tmp_path):
    reading = json.loads((report_cmd.READING).read_text())
    reading["readings"][0]["transcripts"] = reading["readings"][0]["transcripts"][:4]
    path = tmp_path / "reading.json"
    path.write_text(json.dumps(reading))
    _, missing = report_cmd.generate(reading_path=path)
    assert any("read 4 of the 10 required" in m for m in missing)


def test_the_reading_names_real_failing_transcripts_and_findings():
    reading = json.loads(report_cmd.READING.read_text())
    [entry] = reading["readings"]
    assert entry["grader"] == "happy_path" and len(entry["transcripts"]) >= 10 and entry["findings"].strip()
