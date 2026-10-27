import json

from training import reader_report


def test_the_reader_report_meets_its_floors_and_is_byte_identical_across_runs(dataset, tmp_path):
    a = reader_report.run(tmp_path / "a", n_boot=30, dataset=dataset)
    reader_report.run(tmp_path / "b", n_boot=30, dataset=dataset)
    for name in ("reader.json", "reader_report.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert a["dev"]["meets_floor"] and a["dev"]["accuracy"]["value"] >= 0.95
    assert all(not row["below_floor"] for row in a["held_out"]["with_cues"])
    assert any(row["below_floor"] for row in a["held_out"]["without_cues"])  # the finding the cues fix
    assert a["injection"]["agreement"] >= 0.95
    assert json.loads((tmp_path / "a" / "reader.json").read_text())["conflict_rule"] in ("confident", "last")
