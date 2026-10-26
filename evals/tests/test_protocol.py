import json

import pytest
from data_gen.llm.client import MockClient
from data_gen.llm.gateway import Budget

from evals.frontier import DEV_MODEL, FINAL_MODEL, build_frontier_system
from evals.ledger import final_runs
from evals.protocol import (MAX_VERSIONS, ProtocolError, check_can_score_dev, freeze, frozen, load_chain,
                            record_dev_score, require_frozen, versions)
from evals.runner import run_suites
from evals.systems import scored_report
import evals.report_tool  # noqa: F401  (imported so a missing module fails here, not in a run)


def score(path, h, model=DEV_MODEL, note=""):
    return record_dev_score(h, "v1", model, {"auc": 0.7}, spend_usd=0.3, note=note, path=path)


def test_at_most_five_prompt_versions_and_the_sixth_is_refused(tmp_path):
    p = tmp_path / "pv.json"
    for i in range(MAX_VERSIONS):
        assert score(p, f"hash{i}")["kind"] == "version"
    with pytest.raises(ProtocolError, match="sixth is refused"):
        score(p, "hash5")
    assert len(versions(p)) == MAX_VERSIONS


def test_the_same_prompt_on_another_model_is_a_dev_run_not_a_new_version(tmp_path):
    p = tmp_path / "pv.json"
    for i in range(MAX_VERSIONS):
        score(p, f"hash{i}")
    assert check_can_score_dev("hash2", p) == "dev_run"  # allowed even at the cap
    assert score(p, "hash2", FINAL_MODEL)["kind"] == "dev_run" and len(versions(p)) == MAX_VERSIONS


def test_editing_an_earlier_entry_is_detected_on_load(tmp_path):
    p = tmp_path / "pv.json"
    score(p, "a"), score(p, "b")
    data = json.loads(p.read_text())
    data["entries"][0]["metrics"]["auc"] = 0.99
    p.write_text(json.dumps(data))
    with pytest.raises(ProtocolError, match="edited"):
        load_chain(p)
    data = json.loads(p.read_text())  # removing an entry is caught as well
    data["entries"][0]["metrics"]["auc"] = 0.7
    del data["entries"][0]
    p.write_text(json.dumps(data))
    with pytest.raises(ProtocolError):
        load_chain(p)


def test_protected_splits_need_the_frozen_prompt_and_nothing_else(tmp_path):
    p = tmp_path / "pv.json"
    for split in ("test", "adversarial"):
        with pytest.raises(ProtocolError, match="frozen prompt"):
            require_frozen("a", split, p)
    score(p, "a"), score(p, "b")
    with pytest.raises(ProtocolError, match="scored on dev"):
        freeze("never-scored", path=p)
    freeze("a", path=p)
    require_frozen("a", "test", p)
    with pytest.raises(ProtocolError, match="must use the frozen prompt"):
        require_frozen("b", "adversarial", p)
    with pytest.raises(ProtocolError, match="frozen"):
        score(p, "c")  # iteration is over
    assert frozen(p)["prompt_hash"] == "a"


def mock_system(tmp_path, text=None, model=FINAL_MODEL):
    def respond(system, prompt):
        return json.dumps(scored_report(json.loads(prompt), 0.3, uncertain=False))

    client = MockClient(responder=respond)
    sysm = build_frontier_system("v1", model, client, tmp_path / "cache.jsonl", Budget(10_000, 1000.0, 2.0, 10.0))
    if text is not None:
        sysm.system_prompt = text
        from evals.prompt_system import prompt_hash
        sysm.prompt_hash = prompt_hash(text)
    return sysm, client


def test_a_protected_run_before_a_freeze_makes_no_call_and_no_ledger_entry(dataset, tmp_path):
    sysm, client = mock_system(tmp_path)
    ledger = tmp_path / "ledger.json"
    with pytest.raises(ProtocolError):
        run_suites(dataset, sysm, "test", suites=["happy_path"], limit=5, final=True, log_dir=tmp_path / "l",
                   ledger_path=ledger, protocol_path=tmp_path / "pv.json")
    assert client.calls == [] and not ledger.exists()


def test_a_final_run_with_another_prompt_hash_is_refused_and_the_frozen_one_runs(dataset, tmp_path):
    pv, ledger = tmp_path / "pv.json", tmp_path / "ledger.json"
    sysm, client = mock_system(tmp_path)
    score(pv, sysm.prompt_hash), freeze(sysm.prompt_hash, path=pv)
    other, other_client = mock_system(tmp_path, text=sysm.system_prompt + "\nBe terse.")
    with pytest.raises(ProtocolError, match="frozen prompt"):
        run_suites(dataset, other, "adversarial", suites=["adversarial"], limit=5, final=True, log_dir=tmp_path / "l1",
                   ledger_path=ledger, protocol_path=pv)
    assert other_client.calls == []
    run_suites(dataset, sysm, "test", suites=["happy_path"], limit=5, final=True, log_dir=tmp_path / "l2",
               ledger_path=ledger, protocol_path=pv)
    assert len(client.calls) == 5 and final_runs(sysm.version, "test", ledger) == 1


def test_dev_runs_do_not_need_a_freeze(dataset, tmp_path):
    sysm, client = mock_system(tmp_path, model=DEV_MODEL)
    run_suites(dataset, sysm, "dev", suites=["happy_path"], limit=5, log_dir=tmp_path / "l",
               protocol_path=tmp_path / "pv.json")
    assert len(client.calls) == 5
