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
    name: str  # canonical surface form, used by the template renderers and their parser
    base_rate: float
    # Wording an LLM-written note may use for this symptom (includes the canonical name). No phrase is
    # shared with, or contained in, another symptom's phrases, so a mention maps to one symptom.
    phrases: tuple[str, ...] = ()


SYMPTOMS: tuple[SymptomDef, ...] = (
    SymptomDef("tremor", "tremor", 0.20,
               ("tremor", "shaking", "shaky hands", "tremulous")),
    SymptomDef("fatigue", "fatigue", 0.35,
               ("fatigue", "tired", "low energy", "exhausted")),
    SymptomDef("photophobia", "photophobia", 0.15,
               ("photophobia", "light sensitivity", "sensitive to bright light", "bothered by bright lights")),
    SymptomDef("joint_stiffness", "joint stiffness", 0.30,
               ("joint stiffness", "stiff joints", "achy stiff joints", "morning stiffness")),
    SymptomDef("dizziness", "dizziness", 0.25,
               ("dizziness", "lightheaded", "woozy", "dizzy spells")),
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


# Wording an LLM-written note may use, by how the note states the symptom. Separate pools for each polarity avoid
# the awkward negations ("feels not exhausted") that come from negating a pool of positive phrases. No phrase of one
# symptom equals or contains a phrase of another, so a mention maps to one symptom (tested). Notes use ONE phrase.
PHRASEBANK: dict[str, dict[str, tuple[str, ...]]] = {
    "tremor": {
        "present": ("tremor", "shaky hands", "hand tremor", "trembling hands", "tremulous", "shaking of the hands"),
        "hedged": ("possible tremor", "maybe some shaking", "slight tremor at times", "?tremor",
                   "occasional shaky hands", "hands feel a little shaky"),
        "negated": ("no tremor", "denies tremor", "no shaking", "hands steady", "no shaky hands", "denies shaking"),
    },
    "fatigue": {
        "present": ("fatigue", "tired", "low energy", "exhausted", "wiped out", "tires easily"),
        "hedged": ("possibly fatigued", "somewhat tired", "tired on and off", "low energy at times",
                   "maybe more tired than usual", "mild fatigue at times"),
        "negated": ("no fatigue", "denies fatigue", "no tiredness", "energy level normal", "denies low energy",
                    "no exhaustion"),
    },
    "photophobia": {
        "present": ("photophobia", "light sensitivity", "sensitive to bright light", "bothered by bright lights",
                    "light bothers the eyes", "squinting in bright light"),
        "hedged": ("possible light sensitivity", "mild light sensitivity at times", "maybe bothered by bright lights",
                   "slightly sensitive to bright light", "?photophobia", "bright light occasionally bothersome"),
        "negated": ("no photophobia", "denies photophobia", "no light sensitivity", "no trouble with bright lights",
                    "no sensitivity to bright light", "denies light sensitivity"),
    },
    "joint_stiffness": {
        "present": ("joint stiffness", "stiff joints", "achy stiff joints", "morning stiffness",
                    "stiffness in the joints", "joints feel stiff"),
        "hedged": ("possible joint stiffness", "some morning stiffness at times", "joints a bit stiff",
                   "occasional stiff joints", "mild stiffness in the joints", "maybe some stiff joints"),
        "negated": ("no joint stiffness", "denies joint stiffness", "joints not stiff", "no morning stiffness",
                    "no stiff joints", "denies stiffness"),
    },
    "dizziness": {
        "present": ("dizziness", "lightheaded", "woozy", "dizzy spells", "feels dizzy", "dizzy"),
        "hedged": ("possible dizziness", "occasionally lightheaded", "a little woozy at times", "dizzy on and off",
                   "maybe some dizziness", "brief dizzy spells"),
        "negated": ("no dizziness", "denies dizziness", "no lightheadedness", "no dizzy spells", "denies lightheadedness",
                    "no wooziness"),
    },
}
_STATED_TO_POOL = {"present": "present", "hedged": "hedged", "negated": "negated"}


def symptom_phrase_pool(key: str, stated: str) -> tuple[str, ...]:
    """The wording options for a symptom stated as present, hedged or negated."""
    return PHRASEBANK[key][_STATED_TO_POOL[stated]]


def all_symptom_phrases(key: str) -> tuple[str, ...]:
    """Every phrase that counts as a mention of this symptom, whatever its polarity."""
    pools = PHRASEBANK[key].values()
    return tuple(dict.fromkeys([*SYMPTOM_BY_KEY[key].phrases, *(p for pool in pools for p in pool)]))


# Words that show a note mentions a symptom at all (lenient: the exact phrase need not be one of the offered ones, and
# the polarity is judged separately by the independent extractor).
SYMPTOM_STEMS: dict[str, str] = {
    "tremor": r"\b(tremor|tremul|trembl|shak|steady)",
    "fatigue": r"\b(fatigue|tired|exhaust|low energy|energy|wiped)",
    "photophobia": r"\b(photophob|light sensitiv|sensitiv\w* to (bright )?light|bright light|squint)",
    "joint_stiffness": r"\b(stiff)",
    "dizziness": r"\b(dizz|lighthead|woozy|woozi)",
}


def glossary_rows() -> list[dict]:
    """The fictional lab panel as a rater should see it. The rating app ships a copy (rating_ui/lib/glossary.json);
    a test keeps the two identical. No weights, coefficients or scoring data."""
    rows = []
    for lab in LABS:
        row = {"name": lab.name, "abbr": lab.abbr, "unit": "" if lab.unit == "ratio" else lab.unit,
               "ref_lo": lab.ref_lo, "ref_hi": lab.ref_hi}
        if lab.alt_unit:  # some labs report in a second unit; both are normal in real charts
            row["alt_unit"] = lab.alt_unit
            row["alt_ref_lo"] = float(f"{lab.to_alt(lab.ref_lo):.3g}")
            row["alt_ref_hi"] = float(f"{lab.to_alt(lab.ref_hi):.3g}")
        rows.append(row)
    return rows
