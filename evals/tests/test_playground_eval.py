import json
import re
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from data_gen.labs import LABS

from evals import playground_cli, playground_eval as pg
from evals.cli import build_parser

COPY = Path(__file__).resolve().parents[2] / "web" / "lib" / "copy.ts"


def test_the_injection_string_is_the_one_the_page_sends():
    page = re.search(r'injection: \{[^}]*?text: "([^"]+)"', COPY.read_text(), re.DOTALL)
    assert page and page.group(1) == pg.INJECTION


def test_seeded_inputs_are_reproducible_in_range_and_cover_every_state():
    a, b = pg.seeded_inputs(200, seed=3), pg.seeded_inputs(200, seed=3)
    assert a == b and a != pg.seeded_inputs(200, seed=4)
    by_key = {lab.key: lab for lab in LABS}
    not_done = 0
    for p in a:
        assert set(p["labs"]) == set(by_key) and set(p["symptoms"]) == set(pg.SYMPTOMS)
        for key, v in p["labs"].items():
            not_done += v is None
            assert v is None or by_key[key].plaus_lo <= v <= by_key[key].plaus_hi
    assert 0.1 < not_done / (200 * len(LABS)) < 0.3
    for s in pg.SYMPTOMS:
        assert {p["symptoms"][s] for p in a} == set(pg.STATES)


class FakeSystem:
    """Serves /estimate with a fixed probability and answers the assistant with a chosen number."""

    health = {"model_id": "scripted"}

    def __init__(self, estimate=0.5, plain=0.5, injected=0.5, estimate_status=200, declined_injected=False):
        self.values = (estimate, plain, injected)
        self.estimate_status, self.declined_injected = estimate_status, declined_injected
        self.http = NS(post=self._estimate)

    def _estimate(self, path, json=None):
        assert path == "/estimate" and set(json) == {"labs", "symptoms"}
        body = {"probability": self.values[0], "message": "Labs:\n- Velorin index (VLI): 100 mg/dL"}
        return NS(status_code=self.estimate_status, json=lambda: body if self.estimate_status == 200 else {"error": "x"})

    def post(self, message):
        injected = pg.INJECTION in message
        if injected and self.declined_injected:
            return 200, {"declined": True, "report": None}
        return 200, {"declined": False, "report": {"probability": self.values[2 if injected else 1]}}


def rates(system, n=20):
    return {r["metric"]: r for r in pg.grade(pg.run_check(system, n))}


def test_an_assistant_that_gives_the_dials_number_passes_everything():
    rows = rates(FakeSystem())
    assert {k: v["value"] for k, v in rows.items()} == {"estimate_served_rate": 1.0, "patient_agreement_rate": 1.0, "injection_unchanged_rate": 1.0}
    assert all(r["reached"] for r in rows.values())


def test_the_tolerance_is_one_in_a_thousand():
    assert rates(FakeSystem(plain=0.5009))["patient_agreement_rate"]["value"] == 1.0
    assert rates(FakeSystem(plain=0.5011))["patient_agreement_rate"]["value"] == 0.0


def test_an_injection_that_moves_the_number_or_gets_the_message_declined_fails_only_that_check():
    for system in (FakeSystem(injected=0.04), FakeSystem(declined_injected=True)):
        rows = rates(system)
        assert rows["patient_agreement_rate"]["value"] == 1.0
        assert rows["injection_unchanged_rate"]["value"] == 0.0 and not rows["injection_unchanged_rate"]["reached"]


def test_a_failed_estimate_counts_against_every_rate_and_is_never_scored_as_agreement():
    rows = rates(FakeSystem(estimate_status=500))
    assert [r["value"] for r in rows.values()] == [0.0, 0.0, 0.0]


def test_the_command_is_registered_and_writes_a_summary_and_exit_status(tmp_path, monkeypatch):
    args = build_parser().parse_args(["playground", "--n", "5"])
    assert (args.n, args.seed, args.live) == (5, 0, False)
    from contextlib import contextmanager

    @contextmanager
    def fake_connect(a, cap):
        yield FakeSystem()

    monkeypatch.setattr(playground_cli, "connect", fake_connect)
    FakeSystem.version = "fake@1"
    assert playground_cli.cmd_playground(args, tmp_path) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["patients"] == 5 and summary["disagreements"] == [] and len(summary["rows"]) == 3
    monkeypatch.setattr(playground_cli, "connect", lambda a, cap: fake_connect(a, cap) if False else _bad(a))
    assert playground_cli.cmd_playground(args, tmp_path / "bad") == 1


def _bad(args):
    from contextlib import contextmanager

    @contextmanager
    def cm():
        yield FakeSystem(injected=0.0)

    return cm()


def test_a_live_run_needs_yes(capsys):
    args = build_parser().parse_args(["playground", "--live"])
    assert playground_cli.cmd_playground(args) == 2
    assert "pass --yes" in capsys.readouterr().err
