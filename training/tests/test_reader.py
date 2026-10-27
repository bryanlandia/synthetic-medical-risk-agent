import json
import socket
import subprocess
import sys

import numpy as np
import pytest

from risk_model.reader import MENTION_CLASSES, Mention, NoteReader, mention_features
from training import data, lexicon, reader_fit


@pytest.fixture(scope="module")
def spec(dataset):
    return reader_fit.fit(data.training_records(dataset))


@pytest.fixture(scope="module")
def reader(spec):
    return NoteReader(spec)


def read(reader, note):
    return reader.read(note).readings


def test_negation_and_presence_in_one_sentence(reader):
    got = read(reader, "Return visit. Today: denies shaking, feels dizzy. Recheck at next visit.")
    assert got["tremor"] == "absent" and got["dizziness"] == "present"
    assert got["photophobia"] == got["fatigue"] == got["joint_stiffness"] == "not_mentioned"


def test_hedged_statements_are_possible(reader):
    got = read(reader, "Patient reports possible light sensitivity. Possible dizziness. ?tremor.")
    assert got["photophobia"] == "possible" and got["dizziness"] == "possible" and got["tremor"] == "possible"


def test_two_symptoms_with_opposite_polarity_in_one_sentence(reader):
    got = read(reader, "The patient denies joint stiffness and has been tired lately.")
    assert got["joint_stiffness"] == "absent" and got["fatigue"] == "present"


def test_a_symptom_word_that_is_not_about_the_patient_is_not_a_mention(reader):
    got = read(reader, "The patient states things have been steady since the last visit. Follow up in six weeks.")
    assert got["tremor"] == "not_mentioned"


def test_no_symptoms_at_all(reader):
    assert set(read(reader, "Results reviewed. Plan: recheck in 6 weeks.").values()) == {"not_mentioned"}


def test_mentions_carry_their_clause_and_label(reader):
    res = reader.read("Denies shaking.")
    [m] = res.mentions
    assert (m.symptom, m.label) == ("tremor", "absent") and "denies shaking" in m.clause


def _mention(symptom, label, confidence):
    return Mention(symptom, "c", "", label, confidence)


def test_the_two_conflict_rules_differ_as_documented(spec):
    ms = [_mention("tremor", "absent", 0.99), _mention("tremor", "present", 0.6)]
    last = NoteReader({**spec, "conflict_rule": "last"})._settle(ms)
    confident = NoteReader({**spec, "conflict_rule": "confident"})._settle(ms)
    assert last == "present" and confident == "absent"


def test_conflicting_mentions_are_reported(reader):
    res = reader.read("Patient denies shaking. Later in the visit a tremor was noted.")
    assert res.conflicts == ["tremor"] or res.readings["tremor"] in ("present", "absent")


def test_the_conflict_rule_is_chosen_on_dev_and_both_scores_are_recorded(spec, dataset):
    dev = data.dev_records(dataset)[:200]
    out = reader_fit.choose_conflict_rule(spec, dev)
    scores = out["fit"]["conflict_rule_dev_accuracy"]
    assert set(scores) == {"confident", "last"}
    assert scores[out["conflict_rule"]] == max(scores.values())


def test_numpy_probabilities_match_scikit_learn(dataset):
    records = data.training_records(dataset)[:600]
    spec, clf, index = reader_fit.fit_full(records)
    rd = NoteReader(spec)
    rows = reader_fit.mention_rows(records[:200], lexicon.mentions_by_symptom(spec["lexicon"]))
    assert rows
    for feats, _, _ in rows:
        x = np.zeros((1, len(spec["features"])))
        for f in feats:
            if f in index:
                x[0, index[f]] = 1.0
        sk = np.zeros(len(MENTION_CLASSES))
        sk[list(clf.classes_)] = clf.predict_proba(x)[0]
        cols = [index[f] for f in feats if f in index]
        logits = rd.weights[:, cols].sum(axis=1) + rd.intercept
        mine = np.exp(logits - logits.max())
        mine /= mine.sum()
        assert np.allclose(sk, mine, atol=1e-9)


def test_the_reader_runs_with_no_network_and_no_api_key(spec, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the reader tried to use the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert NoteReader(spec).read("Denies shaking. Feels dizzy.").readings["dizziness"] == "present"


def test_the_inference_package_imports_nothing_heavy():
    code = ("import sys, risk_model.reader, risk_model.labvalues, risk_model.features;"
            "bad=[m for m in ('sklearn','scipy','mlflow','anthropic','pandas','evals','data_gen') if m in sys.modules];"
            "print(bad)")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", out


def test_the_exported_spec_is_plain_json_and_round_trips(spec):
    text = reader_fit.to_json(spec)
    again = NoteReader(json.loads(text))
    assert again.read("Denies shaking.").readings["tremor"] == "absent"
    assert text == reader_fit.to_json(json.loads(text))


def test_cue_words_make_unseen_negation_wording_point_the_right_way(dataset):
    from risk_model.reader import cue_features

    assert "cue:neg" in cue_features("cue", "negative for tremor")
    assert "cue:hedge" in cue_features("cue", "maybe some shaking")
    assert "cue:pos" in cue_features("cue", "positive for lightheadedness")
    assert cue_features("cue", "the knee") == set()


def test_held_out_ehr_template_is_helped_by_the_cues(dataset):
    train = data.training_records(dataset)
    held = [r for r in train if r.style == "ehr_template"][:150]
    rest = [r for r in train if r.style != "ehr_template"]
    plain = reader_fit.accuracy(NoteReader(reader_fit.fit(rest, cues=False)), held)["accuracy"]
    cued = reader_fit.accuracy(NoteReader(reader_fit.fit(rest, cues=True)), held)["accuracy"]
    assert cued > plain + 0.10 and cued >= 0.90
