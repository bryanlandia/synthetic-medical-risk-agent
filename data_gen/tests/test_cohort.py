import inspect
import json

import numpy as np
import pytest

from data_gen.cohort import build_patient, generate_cohort
from data_gen.config import GenConfig
from data_gen.labs import LABS, LAB_BY_KEY, SYMPTOM_KEYS
from data_gen.rule import calibrated_intercept, true_probability


def dump(patients):
    return json.dumps([p.__dict__ for p in patients], sort_keys=True)


# --- 3.1 scoring rule -----------------------------------------------------

def test_rule_takes_only_ground_truth_features():
    params = list(inspect.signature(true_probability).parameters)
    assert params == ["labs", "flags", "intercept"]  # no note text anywhere


def test_true_probability_in_unit_interval_and_recomputable():
    ic = calibrated_intercept(0.30)
    for i in range(300):
        p = build_patient(5, i, ic)
        assert 0.0 <= p.true_probability <= 1.0
        assert p.true_probability == pytest.approx(true_probability(p.labs, p.flags, ic))


def test_rule_direction_makes_sense():
    ic = calibrated_intercept(0.30)
    mid = {l.key: l.mean for l in LABS}
    none = {k: False for k in SYMPTOM_KEYS}
    high = dict(mid, velorin_index=LAB_BY_KEY["velorin_index"].mean + 40)
    assert true_probability(high, none, ic) > true_probability(mid, none, ic)
    sick = dict(none, tremor=True, photophobia=True)
    assert true_probability(mid, sick, ic) > true_probability(mid, none, ic)


# --- 3.2 calibration, labels, prevalence ---------------------------------

def test_labels_match_true_probability_per_bin():
    # The spec scenario says "at least 10,000" patients. A larger cohort is used because at
    # exactly 10,000 the top bins hold only a few hundred patients and binomial noise alone
    # (about +/-0.03) makes a fixed 0.03 tolerance flaky.
    ic = calibrated_intercept(0.30)
    ps = [build_patient(1, i, ic) for i in range(60_000)]
    p = np.array([x.true_probability for x in ps])
    y = np.array([x.label for x in ps])
    for b in range(10):
        m = (p >= b / 10) & (p < (b + 1) / 10 + (1e-9 if b == 9 else 0))
        assert m.sum() > 500, f"bin {b} too sparse"
        assert abs(y[m].mean() - p[m].mean()) < 0.03, b


@pytest.mark.parametrize("target", [0.15, 0.30, 0.45])
def test_prevalence_within_tolerance_of_target(target):
    cfg = GenConfig(seed=3, n_train=8000, n_test=2000, target_prevalence=target)
    ps = generate_cohort(cfg)
    assert len(ps) == 10_000
    prevalence = np.mean([p.label for p in ps])
    assert abs(prevalence - target) < 0.02


def test_labels_are_deterministic_per_patient():
    ic = calibrated_intercept(0.30)
    assert build_patient(9, 17, ic) == build_patient(9, 17, ic)


def test_patient_independent_of_cohort_size():
    ic = calibrated_intercept(0.30)
    small = generate_cohort(GenConfig(seed=4, n_train=40, n_test=10))
    assert build_patient(4, 7, ic).labs == small[7].labs


# --- 3.3 splits ---------------------------------------------------------

@pytest.fixture(scope="module")
def default_cohort():
    cfg = GenConfig()
    return cfg, generate_cohort(cfg)


def test_split_sizes_and_disjointness(default_cohort):
    cfg, ps = default_cohort
    train = [p for p in ps if p.split == "train"]
    test = [p for p in ps if p.split == "test"]
    assert abs(len(train) - cfg.n_train) <= 1 and abs(len(test) - cfg.n_test) <= 1
    assert len(train) + len(test) == len(ps)
    ids = [p.patient_id for p in ps]
    assert len(set(ids)) == len(ids)
    assert not ({p.patient_id for p in train} & {p.patient_id for p in test})


def test_random_test_matches_train_distribution(default_cohort):
    _, ps = default_cohort
    train = [p for p in ps if p.split == "train"]
    test = [p for p in ps if p.split == "test"]
    assert abs(np.mean([p.label for p in train]) - np.mean([p.label for p in test])) <= 0.02
    for lab in LABS:
        a = np.array([p.labs[lab.key] for p in train])
        b = np.array([p.labs[lab.key] for p in test])
        assert abs(a.mean() - b.mean()) < 0.1 * lab.sd, lab.key


def test_split_is_unbiased_across_seeds():
    # At 4000/1000 the train/test mean gap has SD ~0.035 SD-units, so a fixed 0.1 tolerance fails
    # for roughly 3% of seeds by chance alone (the default seed is checked above). This test looks
    # for systematic bias: no lab should ever show a gap beyond 4 sigma, and the average gap is ~0.
    gaps = []
    for seed in range(6):
        ps = generate_cohort(GenConfig(seed=seed))
        train = [p for p in ps if p.split == "train"]
        test = [p for p in ps if p.split == "test"]
        for lab in LABS:
            a = np.mean([p.labs[lab.key] for p in train])
            b = np.mean([p.labs[lab.key] for p in test])
            gaps.append((a - b) / lab.sd)
    assert max(abs(g) for g in gaps) < 0.15
    assert abs(np.mean(gaps)) < 0.02


def test_present_values_in_plausible_range(default_cohort):
    _, ps = default_cohort
    for p in ps:
        for lab in LABS:
            assert lab.plaus_lo <= p.labs[lab.key] <= lab.plaus_hi


# --- 2.3 reproducibility (completes the seed-handling task) ---------------

def test_same_seed_is_byte_identical_and_different_seed_differs():
    a = generate_cohort(GenConfig(seed=11, n_train=300, n_test=100))
    b = generate_cohort(GenConfig(seed=11, n_train=300, n_test=100))
    c = generate_cohort(GenConfig(seed=12, n_train=300, n_test=100))
    assert dump(a) == dump(b)
    assert dump(a) != dump(c)
    assert not ({p.patient_id for p in a} & {p.patient_id for p in c})
