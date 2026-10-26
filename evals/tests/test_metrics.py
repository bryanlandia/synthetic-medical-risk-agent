import numpy as np
import pytest

from evals.metrics import auc, bootstrap, brier, compare, ece, interval, log_loss


def test_auc_matches_hand_computed_values():
    assert auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert auc([0, 1], [0.2, 0.9]) == 1.0 and auc([0, 1], [0.9, 0.2]) == 0.0
    assert auc([0, 0, 1, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5  # all tied
    assert auc([0, 1, 1, 0], [0.3, 0.3, 0.7, 0.1]) == pytest.approx((1 + 0.5 + 1 + 1) / 4)  # one tie across classes
    assert np.isnan(auc([1, 1], [0.2, 0.9]))  # one class only


def test_brier_log_loss_and_ece_match_hand_computed_values():
    y, p = [0, 1, 1, 0], [0.2, 0.9, 0.6, 0.4]
    assert brier(y, p) == pytest.approx((0.04 + 0.01 + 0.16 + 0.16) / 4)
    assert log_loss(y, p) == pytest.approx(-(np.log(0.8) + np.log(0.9) + np.log(0.6) + np.log(0.6)) / 4)
    assert log_loss([1], [0.0]) < 40  # clipped, not infinite
    assert ece([0, 1], [0.0, 1.0]) == 0.0  # perfectly confident and right
    assert ece([1, 1, 0, 0], [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.0)  # a 50% forecast that is right half the time
    assert ece([1, 1, 1, 1], [0.1, 0.1, 0.1, 0.1]) == pytest.approx(0.9)  # a 10% forecast that always happens


def test_clustering_by_patient_widens_the_interval():
    rng = np.random.default_rng(0)
    base = rng.random(100) < 0.3
    y = np.repeat(base.astype(float), 4)  # each patient appears four times (matched pairs), identically
    keys = [f"p{i}" for i in np.repeat(np.arange(100), 4)]
    clustered = interval(np.mean, [y], keys, n_boot=500, seed=1)
    naive = interval(np.mean, [y], keys, n_boot=500, seed=1, cluster=False)
    assert (clustered["hi"] - clustered["lo"]) > 1.4 * (naive["hi"] - naive["lo"])
    assert clustered["patients"] == 100 and clustered["n"] == 400


def test_a_patient_is_drawn_together():
    y = np.array([0, 0, 1, 1], dtype=float)
    keys = ["a", "a", "b", "b"]
    draws = bootstrap(np.mean, [y], keys, n_boot=200, seed=3)
    assert set(np.round(draws, 6)) <= {0.0, 0.5, 1.0}  # only whole patients: never a mix inside one patient


def test_intervals_are_reproducible_and_stable_across_seeds():
    rng = np.random.default_rng(5)
    y = (rng.random(300) < 0.4).astype(float)
    p = np.clip(y * 0.3 + rng.random(300) * 0.7, 0, 1)
    keys = [f"p{i}" for i in range(300)]
    a = interval(auc, [y, p], keys, n_boot=1000, seed=7)
    b = interval(auc, [y, p], keys, n_boot=1000, seed=7)
    c = interval(auc, [y, p], keys, n_boot=1000, seed=8)
    assert a == b
    width = a["hi"] - a["lo"]
    assert abs(a["lo"] - c["lo"]) < 0.1 * width and abs(a["hi"] - c["hi"]) < 0.1 * width


def test_minimum_detectable_difference_and_the_below_flag():
    rng = np.random.default_rng(9)
    n = 400
    y = (rng.random(n) < 0.3).astype(float)
    good = np.clip(y * 0.5 + rng.random(n) * 0.5, 0, 1)
    noisy = np.clip(good + rng.normal(0, 0.02, n), 0, 1)  # nearly identical to `good`
    keys = [f"p{i}" for i in range(n)]
    similar = compare(brier, [y, good], [y, noisy], keys, n_boot=300, seed=2)
    assert similar["below_mdd"] is True and similar["mdd"] > 0
    far = compare(brier, [y, good], [y, np.full(n, 0.3)], keys, n_boot=300, seed=2)
    assert far["below_mdd"] is False and far["diff"] < 0  # good has a lower Brier than the constant
    assert far["lo"] < far["diff"] < far["hi"]
