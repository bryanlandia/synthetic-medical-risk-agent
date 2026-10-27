"""Fit the mention classifier from train records and export the reader. Labels come from the plan symptoms."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from evals.graders import true_symptom_readings
from sklearn.linear_model import LogisticRegression

from risk_model.reader import MENTION_CLASSES, NoteReader, find_mentions, mention_features
from risk_model.labs import SYMPTOM_KEYS

from . import lexicon as lex

MIN_DF = 3


def mention_rows(records, patterns, cues: bool = True) -> list[tuple[list[str], str, str]]:
    """(features, label, patient id) for every lexicon hit; the label is the record's stated reading or 'none'."""
    rows = []
    for r in records:
        truth = true_symptom_readings(r)
        for symptom, clause, previous in find_mentions(r.input.note.lower(), patterns):
            label = truth[symptom] if truth[symptom] != "not_mentioned" else "none"
            rows.append((mention_features(symptom, clause, previous, cues), label, r.patient_id))
    return rows


def fit_full(records, lexicon: dict[str, list[str]] | None = None, c: float = 1.0, seed: int = 0,
             conflict_rule: str = "confident", cues: bool = True):
    """(the reader spec, the fitted scikit-learn model, the feature index). The spec is a plain dictionary, ready to
    be written as JSON; the other two are for tests that compare the numpy path with scikit-learn."""
    lexicon = lexicon or lex.load()
    rows = mention_rows(records, lex.mentions_by_symptom(lexicon), cues)
    counts: dict[str, int] = {}
    for feats, _, _ in rows:
        for f in feats:
            counts[f] = counts.get(f, 0) + 1
    names = sorted(f for f, n in counts.items() if n >= MIN_DF)
    index = {f: i for i, f in enumerate(names)}
    x = np.zeros((len(rows), len(names)))
    for i, (feats, _, _) in enumerate(rows):
        for f in feats:
            if f in index:
                x[i, index[f]] = 1.0
    y = np.array([MENTION_CLASSES.index(label) for _, label, _ in rows])
    clf = LogisticRegression(C=c, max_iter=2000, random_state=seed).fit(x, y)
    classes = list(clf.classes_)
    weights = np.zeros((len(MENTION_CLASSES), len(names)))
    intercept = np.full(len(MENTION_CLASSES), -50.0)  # a class never seen in training is effectively impossible
    for row, k in enumerate(classes):
        weights[k], intercept[k] = clf.coef_[row], clf.intercept_[row]
    spec = {"lexicon": lexicon, "classes": list(MENTION_CLASSES), "features": names,
            "weights": weights.tolist(), "intercept": intercept.tolist(), "conflict_rule": conflict_rule,
            "cues": cues, "fit": {"c": c, "seed": seed, "n_mentions": len(rows), "min_df": MIN_DF}}
    return spec, clf, index


def fit(records, lexicon: dict[str, list[str]] | None = None, c: float = 1.0, seed: int = 0,
        conflict_rule: str = "confident", cues: bool = True) -> dict[str, Any]:
    return fit_full(records, lexicon, c, seed, conflict_rule, cues)[0]


CONFLICT_RULES = ("confident", "last")


def choose_conflict_rule(spec: dict[str, Any], dev_records) -> dict[str, Any]:
    """Score both rules for a note whose mentions of one symptom disagree, on dev, and keep the better one (a tie keeps
    'confident'). Returns the spec with the choice and both accuracies recorded."""
    scores = {rule: accuracy(NoteReader({**spec, "conflict_rule": rule}), dev_records)["accuracy"] for rule in CONFLICT_RULES}
    best = max(CONFLICT_RULES, key=lambda r: (scores[r], r == "confident"))
    return {**spec, "conflict_rule": best, "fit": {**spec["fit"], "conflict_rule_dev_accuracy": scores}}


def predict_all(reader: NoteReader, records) -> list[dict[str, str]]:
    return [reader.read(r.input.note).readings for r in records]


def accuracy(reader: NoteReader, records) -> dict[str, float]:
    """Symptom-reading accuracy over records x symptoms, and per symptom, against the plan's stated readings."""
    hits = {k: [] for k in SYMPTOM_KEYS}
    for r in records:
        truth, got = true_symptom_readings(r), reader.read(r.input.note).readings
        for k in SYMPTOM_KEYS:
            hits[k].append(truth[k] == got[k])
    allv = [v for vs in hits.values() for v in vs]
    return {"accuracy": float(np.mean(allv)), **{k: float(np.mean(v)) for k, v in hits.items()}}


def to_json(spec: dict[str, Any]) -> str:
    return json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n"
