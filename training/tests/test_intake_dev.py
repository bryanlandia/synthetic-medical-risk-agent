import re

import pytest
from evals.messages import render_message
from evals.records import input_view
from risk_model import intake
from risk_model.labs import LAB_BY_KEY

from training import agreement, data

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def written(message: str) -> list[float]:
    return [float(x) for x in NUMBER.findall(message)]


def test_every_non_null_panel_value_is_a_number_written_in_its_message(dataset):
    checked = 0
    for r in data.dev_records(dataset):
        message = render_message(input_view(r))
        numbers = written(message)
        for e in intake.view_from_text(message)["panel"]:
            if e["value"] is None:
                continue
            lab = LAB_BY_KEY[e["lab"]]
            options = [e["value"]] + ([e["value"] * lab.factor] if lab.factor else [])  # the alternate-unit spelling
            assert any(abs(n - o) <= 1e-9 * max(1.0, abs(o)) for n in numbers for o in options), (r.patient_id, e)
            checked += 1
    assert checked > 2500


def test_a_lab_the_rendered_message_leaves_out_is_null_unless_the_note_states_it(dataset):
    for r in data.dev_records(dataset)[:200]:
        view = input_view(r)
        text_panel = {e["lab"]: e["value"] for e in intake.view_from_text(render_message(view))["panel"]}
        for e in view["panel"]:
            if e["value"] is None and text_panel[e["lab"]] is not None:
                assert re.search(LAB_BY_KEY[e["lab"]].abbr, view["note"]), (r.patient_id, e["lab"])


def test_the_text_path_agrees_with_the_structured_path_on_dev(dataset):
    res = agreement.check(dataset)
    assert res["records"] == 500 and res["meets_requirement"] and res["share"] >= 0.95
    assert all(e["reasons"] for e in res["exceptions"])  # every exception explains itself


def test_the_agreement_report_lists_exceptions_with_reasons(dataset):
    records = data.dev_records(dataset)[:30]
    res = agreement.check(dataset, records=records)
    res["exceptions"] = [{"patient_id": "P1", "structured": 0.3, "text": 0.4, "difference": 0.1,
                          "reasons": ["velorin_index: panel None became 104.0"]}]
    res["within_tolerance"], res["share"] = res["records"] - 1, (res["records"] - 1) / res["records"]
    text = agreement.render(res)
    assert "P1" in text and "velorin_index: panel None became 104.0" in text and "ALL DATA IS SYNTHETIC" in text
