"""The HIDDEN scoring rule that defines the fictional disease.

Ground truth only. Must not be imported by training/ or agent/ (checked in the integration tasks).
The rule is a pure function of the ground-truth features (labs and symptom flags), never of note text.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .labs import LAB_BY_KEY, LABS, SYMPTOMS
from .seeds import rng_for

# Coefficients on standardized labs z = (x - mean) / sd.
LAB_WEIGHTS: dict[str, float] = {
    "velorin_index": 0.9,
    "serum_k17": -0.5,
    "tarnic_acid": 0.6,
    "brell_enzyme": 0.4,
    "halvin_titer": -0.3,
    "osmet_level": 0.0,  # distractor
    "plexa_count": 0.2,
    "dorrin_ratio": 0.5,
}
FLAG_WEIGHTS: dict[str, float] = {
    "tremor": 0.9,
    "fatigue": 0.4,
    "photophobia": 0.7,
    "joint_stiffness": 0.2,
    "dizziness": 0.3,
}
INTERACTION_VELORIN_TARNIC = 0.35  # z_velorin * z_tarnic
INTERACTION_TREMOR_BRELL = 0.4  # tremor * z_brell

# The disease is a property of the rule, not of any dataset seed.
CALIBRATION_SEED = 0
CALIBRATION_N = 200_000


def z(lab_key: str, x):
    lab = LAB_BY_KEY[lab_key]
    return (x - lab.mean) / lab.sd


def _logit(zs: dict, flags: dict, intercept: float):
    s = intercept
    for k, w in LAB_WEIGHTS.items():
        s = s + w * zs[k]
    for k, w in FLAG_WEIGHTS.items():
        s = s + w * flags[k]
    s = s + INTERACTION_VELORIN_TARNIC * zs["velorin_index"] * zs["tarnic_acid"]
    s = s + INTERACTION_TREMOR_BRELL * flags["tremor"] * zs["brell_enzyme"]
    return s


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def true_probability(labs: dict[str, float], flags: dict[str, bool], intercept: float) -> float:
    zs = {k: z(k, v) for k, v in labs.items()}
    fl = {k: 1.0 if v else 0.0 for k, v in flags.items()}
    return float(_sigmoid(_logit(zs, fl, intercept)))


def trunc_normal(rng: np.random.Generator, mean: float, sd: float, lo: float, hi: float, size=None):
    """Normal restricted to [lo, hi] by redrawing out-of-range values."""
    x = rng.normal(mean, sd, size)
    if size is None:
        while not (lo <= x <= hi):
            x = rng.normal(mean, sd)
        return float(x)
    bad = (x < lo) | (x > hi)
    while bad.any():
        x[bad] = rng.normal(mean, sd, int(bad.sum()))
        bad = (x < lo) | (x > hi)
    return x


@lru_cache(maxsize=None)
def calibrated_intercept(target_prevalence: float) -> float:
    """Intercept making the mean true probability equal the target prevalence."""
    rng = rng_for(CALIBRATION_SEED, "calibration", 0)
    zs = {
        lab.key: z(lab.key, trunc_normal(rng, lab.mean, lab.sd, lab.plaus_lo, lab.plaus_hi, CALIBRATION_N))
        for lab in LABS
    }
    fl = {s.key: (rng.random(CALIBRATION_N) < s.base_rate).astype(float) for s in SYMPTOMS}
    lo, hi = -15.0, 15.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if float(_sigmoid(_logit(zs, fl, mid)).mean()) < target_prevalence:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 6)


def round_sig(x: float, sig: int = 4) -> float:
    return float(f"{x:.{sig}g}")
