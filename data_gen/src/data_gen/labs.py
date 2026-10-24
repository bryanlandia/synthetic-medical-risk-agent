"""Fictional lab and symptom definitions. Safe to import anywhere: contains no scoring-rule coefficients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabDef:
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
    # alt_value = canonical_value * factor
    factor: float | None = None

    def to_alt(self, value: float) -> float:
        assert self.factor is not None
        return value * self.factor

    def from_alt(self, value: float) -> float:
        assert self.factor is not None
        return value / self.factor


LABS: tuple[LabDef, ...] = (
    LabDef("velorin_index", "Velorin index", "VLI", "mg/dL", 100, 20, 70, 130, 20, 220,
           alt_unit="mmol/L", factor=0.0555),
    LabDef("serum_k17", "Serum K-17", "K17", "mmol/L", 4.2, 0.5, 3.4, 5.0, 1.5, 7.5,
           alt_unit="mg/dL", factor=3.91),
    LabDef("tarnic_acid", "Tarnic acid", "TAC", "umol/L", 300, 60, 200, 400, 50, 600,
           alt_unit="mg/dL", factor=0.0168),
    LabDef("brell_enzyme", "Brell enzyme", "BRE", "U/L", 35, 10, 15, 55, 3, 90,
           alt_unit="ukat/L", factor=0.01667),
    LabDef("halvin_titer", "Halvin titer", "HAT", "g/dL", 4.0, 0.6, 3.0, 5.0, 1.5, 7.0),
    LabDef("osmet_level", "Osmet level", "OSM", "mOsm/kg", 290, 12, 270, 310, 230, 350),
    LabDef("plexa_count", "Plexa count", "PLX", "x10^9/L", 250, 55, 150, 400, 40, 600),
    LabDef("dorrin_ratio", "Dorrin ratio", "DOR", "ratio", 1.0, 0.25, 0.6, 1.4, 0.1, 2.5),
)

LAB_BY_KEY: dict[str, LabDef] = {lab.key: lab for lab in LABS}
LAB_KEYS: tuple[str, ...] = tuple(lab.key for lab in LABS)


@dataclass(frozen=True)
class SymptomDef:
    key: str
    name: str  # surface form used in notes
    base_rate: float


SYMPTOMS: tuple[SymptomDef, ...] = (
    SymptomDef("tremor", "tremor", 0.20),
    SymptomDef("fatigue", "fatigue", 0.35),
    SymptomDef("photophobia", "photophobia", 0.15),
    SymptomDef("joint_stiffness", "joint stiffness", 0.30),
    SymptomDef("dizziness", "dizziness", 0.25),
)

SYMPTOM_BY_KEY: dict[str, SymptomDef] = {s.key: s for s in SYMPTOMS}
SYMPTOM_KEYS: tuple[str, ...] = tuple(s.key for s in SYMPTOMS)

# Real clinical test names that must never appear as a fictional lab name.
REAL_TEST_DENYLIST: tuple[str, ...] = (
    "glucose", "cholesterol", "sodium", "potassium", "creatinine", "hemoglobin",
    "haemoglobin", "hematocrit", "platelet", "albumin", "bilirubin", "urea", "bun",
    "calcium", "chloride", "bicarbonate", "triglyceride", "ldl", "hdl", "a1c",
    "tsh", "ferritin", "troponin", "crp", "esr", "alt", "ast", "wbc", "rbc", "inr",
    "lactate", "magnesium", "phosphate", "uric",
)
