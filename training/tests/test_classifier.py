import json

import numpy as np
import pytest

from risk_model.classifier import RiskClassifier
from risk_model.features import FEATURE_NAMES
from training import classifier_fit as cf


def test_the_grid_is_read_from_its_file(tmp_path):
    grid = cf.load_grid()
    assert grid["logistic_c"] == [0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0] and len(grid["logistic_c"]) <= 12
    path = tmp_path / "grid.json"
    path.write_text(json.dumps({**grid, "logistic_c": [0.1, 1.0]}))
    assert cf.load_grid(path)["logistic_c"] == [0.1, 1.0]


def test_a_grid_of_more_than_twelve_candidates_is_refused(tmp_path):
    path = tmp_path / "grid.json"
    path.write_text(json.dumps({**cf.load_grid(), "logistic_c": [0.01 * (i + 1) for i in range(13)], "max_candidates": 13}))
    with pytest.raises(ValueError, match="at most 12"):
        cf.load_grid(path)
    path.write_text(json.dumps({**cf.load_grid(), "logistic_c": [0.01 * (i + 1) for i in range(10)], "max_candidates": 8}))
    with pytest.raises(ValueError, match="at most 8"):
        cf.load_grid(path)


def _toy(n=4000, seed=1, scale=2.0, c=1.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 6))
    z = scale * (x @ np.array([1.0, -0.8, 0.5, 0.0, 0.3, 0.0]))
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
    return cf.fit_logistic(x, y, c, seed=0, folds=5), x, y


def test_platt_scaling_is_kept_for_an_underconfident_model():
    fitted, x, y = _toy(scale=2.0, c=0.003)  # heavy shrinkage makes the logits too small
    assert fitted["platt"] is not None and fitted["platt"]["a"] > 1.5
    assert fitted["oof_log_loss"]["after"] < fitted["oof_log_loss"]["before"]


def test_platt_scaling_is_dropped_for_an_already_calibrated_model():
    fitted, _, _ = _toy(n=20000, scale=1.0, c=1e4)
    assert fitted["platt"] is None
    assert abs(fitted["oof_log_loss"]["after"] - fitted["oof_log_loss"]["before"]) < 1e-3


def test_the_exported_spec_gives_the_same_probabilities_as_the_fitted_model():
    fitted, x, y = _toy()
    k = len(FEATURE_NAMES)
    wide = np.zeros((len(x), k))
    wide[:, :x.shape[1]] = x
    fitted = cf.fit_logistic(wide, y, 1.0, seed=0, folds=5)
    spec = cf.spec_for(fitted, np.zeros(8), np.ones(8), {})
    clf = RiskClassifier(json.loads(json.dumps(spec)))
    z = wide @ np.asarray(fitted["coef"]) + fitted["intercept"]
    if fitted["platt"]:
        z = fitted["platt"]["a"] * z + fitted["platt"]["b"]
    assert np.allclose([clf.logit(row) for row in wide[:50]], z[:50])


def test_contributions_sum_to_the_logit_minus_the_intercept():
    fitted, x, y = _toy()
    wide = np.zeros((len(x), len(FEATURE_NAMES)))
    wide[:, :x.shape[1]] = x
    fitted = cf.fit_logistic(wide, y, 1.0, seed=0, folds=5)
    clf = RiskClassifier(cf.spec_for(fitted, np.zeros(8), np.ones(8), {}))
    row = wide[0]
    scale = 1.0 if clf.platt is None else clf.platt[0]
    assert np.isclose(clf.contributions(row).sum() + scale * clf.intercept + (0 if clf.platt is None else clf.platt[1]), clf.logit(row))
