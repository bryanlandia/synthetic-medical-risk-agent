import json
from collections import Counter

from data_gen.labs import LAB_BY_KEY

from evals import demo_cases as dc
from evals import packet_eval as pe
from evals.devsplit import dev_ids
from evals.messages import render_message
from evals.records import input_view

FORBIDDEN_KEYS = {"ground_truth", "true_probability", "label", "flags", "labs_true", "noise", "tags", "plan"}
REAL_NAMES = ("aetna", "cigna", "humana", "anthem", "kaiser", "unitedhealth", "blue cross", "blue shield", "medicare", "medicaid", "oscar", "centene")


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _committed():
    return json.loads(dc.DEFAULT_OUT.read_text())


def test_thirty_dev_cases_with_the_messages_the_harness_renders(dataset):
    data = _committed()
    dev = set(dev_ids(dataset))
    assert len(data["cases"]) == dc.N_CASES == 30
    for c in data["cases"]:
        assert c["patient_id"] in dev
        assert c["message"] == render_message(input_view(dataset.record(c["patient_id"]))), c["id"]


def test_the_file_carries_no_ground_truth():
    data = _committed()
    assert not FORBIDDEN_KEYS & set(_walk(data))
    for c in data["cases"]:
        assert set(c) == {"id", "ordinal", "request_code", "patient_id", "insurer", "preparer", "received", "chart", "message", "answers"}
        assert set(c["chart"]) == {"labs", "note"}


def test_the_committed_file_is_what_the_builder_writes_and_a_rebuild_is_identical(dataset):
    assert dc.DEFAULT_OUT.read_text() == dc.text(dataset) == dc.text(dataset)


def test_the_chart_matches_the_message():
    for c in _committed()["cases"]:
        stated = [f"- {lab['name']} ({lab['abbr']}): {lab['value']:g} {lab['unit']}" for lab in c["chart"]["labs"] if lab["value"] is not None]
        assert c["message"] == "\n".join(["Labs:", *stated, "", "Note:", c["chart"]["note"]])


def test_the_mix_meets_the_ranges(dataset):
    cases = _committed()["cases"]
    records = [dataset.record(c["patient_id"]) for c in cases]
    c1 = Counter(pe.reference(r, {})["C1"] for r in records)
    assert 8 <= c1["met"] <= 10 and 6 <= c1["unknown"] <= 7 and c1["met"] + c1["unknown"] + c1["unmet"] == 30
    noise = [{n.type for n in r.noise} for r in records]
    assert sum("unit_mismatch" in n for n in noise) >= 3 and sum("contradiction" in n for n in noise) >= 2
    assert sum(0.4 <= r.ground_truth.true_probability <= 0.6 for r in records) >= 3
    assert sum(any(e.value is None for e in r.input.panel) for r in records) >= 3
    from evals.graders import true_symptom_readings
    assert {true_symptom_readings(r)["tremor"] for r in records} == {"present", "possible", "absent", "not_mentioned"}


def test_every_dev_patient_with_c1_and_c2_met_is_included(dataset):
    both = {r.patient_id for r in pe.stage_records(dataset, "dev") if pe.reference(r, {})["C1"] == "met" and pe.reference(r, {})["C2"] == "met"}
    assert len(both) == 3  # there are only three, which is why only three cases can be fully releasable
    assert both <= {c["patient_id"] for c in _committed()["cases"]}


def test_the_packets_would_include_releasable_blocked_and_unmet_cases(dataset):
    cases = _committed()["cases"]
    statuses = [pe.reference(dataset.record(c["patient_id"]), c["answers"]) for c in cases]
    releasable = [s for s in statuses if all(v == "met" for v in s.values())]
    blocked = [s for s in statuses if "unknown" in s.values()]
    unmet_only = [s for s in statuses if "unknown" not in s.values() and "unmet" in s.values()]
    assert len(releasable) >= 3 and len(blocked) >= 5 and len(unmet_only) >= 5


def test_the_preparer_answers_are_mostly_yes_with_some_no_and_some_unanswered():
    answers = [c["answers"] for c in _committed()["cases"]]
    assert all(set(a) == set(pe.ATTESTED) and set(a.values()) <= {"yes", "no", "unanswered"} for a in answers)
    assert sum(all(v == "yes" for v in a.values()) for a in answers) >= 15
    assert sum("no" in a.values() for a in answers) >= 3 and sum("unanswered" in a.values() for a in answers) >= 3


def test_insurers_preparers_and_codes_are_fictional_stable_and_varied():
    cases = _committed()["cases"]
    assert {c["insurer"] for c in cases} <= set(dc.INSURERS) and len({c["insurer"] for c in cases}) >= 6
    assert {c["preparer"] for c in cases} <= set(dc.PREPARERS)
    assert len({c["request_code"] for c in cases}) == 30 and all(c["request_code"].startswith("VK-PET-") for c in cases)
    names = " ".join([*dc.INSURERS, *dc.PREPARERS]).lower()
    assert not [n for n in REAL_NAMES if n in names]
    times = [c["received"] for c in cases]
    assert times == sorted(times) and all("07:30" <= t <= "16:45" for t in times)


def test_each_lab_carries_its_range_and_a_flag_judged_in_the_usual_unit():
    flagged = 0
    for c in _committed()["cases"]:
        for entry in c["chart"]["labs"]:
            lab = LAB_BY_KEY[entry["lab"]]
            assert (entry["ref_lo"], entry["ref_hi"], entry["ref_unit"]) == (lab.ref_lo, lab.ref_hi, lab.unit)
            if entry["value"] is None:
                assert entry["flag"] is None
                continue
            usual = lab.from_alt(entry["value"]) if lab.alt_unit and entry["unit"] == lab.alt_unit else entry["value"]
            assert entry["flag"] == ("H" if usual > lab.ref_hi else "L" if usual < lab.ref_lo else None)
            flagged += entry["flag"] is not None
    assert flagged >= 1


def test_the_flag_is_judged_after_unit_conversion():
    lab = next(l for l in LAB_BY_KEY.values() if l.alt_unit)
    assert dc.flag(lab, lab.to_alt((lab.ref_lo + lab.ref_hi) / 2), lab.alt_unit) is None
    assert dc.flag(lab, lab.to_alt(lab.ref_hi * 1.2), lab.alt_unit) == "H"
    assert dc.flag(lab, None, lab.unit) is None


def test_the_packets_the_service_builds_for_the_30_cases_match_the_reference(dataset):
    """Through the real scripted service: the six statuses equal the independent reference, and the mix has releasable,
    blocked and unmet-only cases."""
    import types

    from evals import packet_cli
    from evals.agent_cli import connect

    cases = _committed()["cases"]
    with connect(types.SimpleNamespace(base_url=None, live=False), 1.0) as system:
        packets = [packet_cli.post_packet(system, c["message"], c["answers"]) for c in cases]
    assert all(p["status"] == 200 and not p["body"].get("declined") for p in packets)
    for c, p in zip(cases, packets):
        assert pe.table(p["body"]) == pe.reference(dataset.record(c["patient_id"]), c["answers"]), c["id"]
    tables = [pe.table(p["body"]) for p in packets]
    assert sum(all(v == "met" for v in t.values()) for t in tables) >= 3
    assert sum("unknown" in t.values() for t in tables) >= 5
    assert sum("unknown" not in t.values() and "unmet" in t.values() for t in tables) >= 5
