"""The fictional lab panel and symptom keys, as the inference package needs them.

A copy of ``data_gen.labs`` so that the agent can load the model without the generator; a test keeps the two
identical. Contains no scoring-rule coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lab:
    key: str
    name: str
    abbr: str
    unit: str
    mean: float
    sd: float
    ref_lo: float
    ref_hi: float
    plaus_lo: float
    plaus_hi: float
    alt_unit: str | None = None
    factor: float | None = None  # alt_value = usual_value * factor

    def to_usual(self, value: float, unit: str | None) -> float:
        """The value in the usual unit; a value in the alternate unit is converted, any other unit is left as it is."""
        if self.alt_unit and unit == self.alt_unit and self.factor:
            return value / self.factor
        return value


LABS: tuple[Lab, ...] = (
    Lab("velorin_index", "Velorin index", "VLI", "mg/dL", 100, 20, 70, 130, 20, 220, "mmol/L", 0.0555),
    Lab("serum_k17", "Serum K-17", "K17", "mmol/L", 4.2, 0.5, 3.4, 5.0, 1.5, 7.5, "mg/dL", 3.91),
    Lab("tarnic_acid", "Tarnic acid", "TAC", "umol/L", 300, 60, 200, 400, 50, 600, "mg/dL", 0.0168),
    Lab("brell_enzyme", "Brell enzyme", "BRE", "U/L", 35, 10, 15, 55, 3, 90, "ukat/L", 0.01667),
    Lab("halvin_titer", "Halvin titer", "HAT", "g/dL", 4.0, 0.6, 3.0, 5.0, 1.5, 7.0),
    Lab("osmet_level", "Osmet level", "OSM", "mOsm/kg", 290, 12, 270, 310, 230, 350),
    Lab("plexa_count", "Plexa count", "PLX", "x10^9/L", 250, 55, 150, 400, 40, 600),
    Lab("dorrin_ratio", "Dorrin ratio", "DOR", "ratio", 1.0, 0.25, 0.6, 1.4, 0.1, 2.5),
)
LAB_BY_KEY: dict[str, Lab] = {lab.key: lab for lab in LABS}
LAB_KEYS: tuple[str, ...] = tuple(lab.key for lab in LABS)
SYMPTOM_KEYS: tuple[str, ...] = ("tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness")
READINGS: tuple[str, ...] = ("present", "possible", "absent", "not_mentioned")
