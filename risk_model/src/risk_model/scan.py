"""Scan-readiness for the fictional K-17 PET-CT policy: criteria, evidence and gaps, all computed by code.

Nothing here calls a model or reads the model's probability to decide a criterion. C1 and C2 come from the chart and the
note's symptom readings; C3 to C6 come only from the clinician's answers. A criterion is met, unmet or unknown, and an
unknown one becomes a gap. A recorded value is never changed.
"""

from __future__ import annotations

from typing import Any

from . import features, policy
from .labs import LAB_BY_KEY, SYMPTOM_KEYS

ANSWERS = ("yes", "no", "unanswered")
SYMPTOM_LABEL = {"tremor": "tremor", "fatigue": "fatigue", "photophobia": "light sensitivity",
                 "joint_stiffness": "joint stiffness", "dizziness": "dizziness"}


def check_attestations(attestations: Any) -> dict[str, str]:
    """The answers as ``{C3..C6: yes|no}``; an unanswered item is left out. Anything else raises ``ValueError``."""
    if attestations is None:
        return {}
    if not isinstance(attestations, dict):
        raise ValueError("attestations must be an object")
    out: dict[str, str] = {}
    for key, value in attestations.items():
        if key not in policy.ATTESTED_IDS:
            raise ValueError(f"attestation for {key!r} is not allowed; only {', '.join(policy.ATTESTED_IDS)}")
        if not isinstance(value, str) or value not in ANSWERS:
            raise ValueError(f"attestation for {key} must be one of {', '.join(ANSWERS)}")
        if value != "unanswered":
            out[key] = value
    return out


def number(value: float) -> str:
    return f"{value:.4g}"


def _with_unit(value: float, unit: str) -> str:
    return f"{number(value)}{'' if unit == 'ratio' else ' ' + unit}"


def _lab_evidence(view: dict[str, Any], key: str, threshold: float) -> dict[str, Any] | None:
    """Evidence for a lab on the chart (usable value, as written with its unit), else None.

    The state is whether the value, in the lab's usual unit, is strictly above the policy threshold. The lab's own reference range
    is given for context and decides nothing."""
    lab = LAB_BY_KEY[key]
    usual = features.panel_values(view)[key]
    if usual is None:
        return None
    entry = next(e for e in view["panel"] if e["lab"] == key)
    above = usual > threshold
    verdict = "above" if above else "not above"
    return {"id": f"lab:{key}", "label": lab.name, "value": float(entry["value"]), "unit": entry["unit"],
            "text": (f"{lab.name} {_with_unit(float(entry['value']), str(entry['unit']))} ({verdict} the policy threshold of "
                     f"{_with_unit(threshold, lab.unit)}; lab reference range {number(lab.ref_lo)} to {_with_unit(lab.ref_hi, lab.unit)})"),
            "state": "above" if above else "not above"}


def _c1(view: dict[str, Any]) -> tuple[str, list[str], list[str], dict[str, dict[str, Any]]]:
    thresholds = policy.load()["c1_thresholds"]
    evidence = {k: e for k, t in thresholds.items() if (e := _lab_evidence(view, k, t))}
    above = [k for k, e in evidence.items() if e["state"] == "above"]
    unreported = [k for k in thresholds if k not in evidence]
    need = policy.load()["c1_min"]
    if len(above) >= need:
        status = "met"
    elif len(above) + len(unreported) < need:
        status = "unmet"
    else:
        status = "unknown"
    cited = above if status == "met" else list(evidence)
    return status, [f"lab:{k}" for k in cited], unreported, evidence


def _c2(symptoms: dict[str, str]) -> tuple[str, list[str], list[str]]:
    required = policy.load()["c2_required"]
    others = [s for s in SYMPTOM_KEYS if s != required]
    present = [s for s in others if symptoms[s] == "present"]
    open_ = [s for s in others if symptoms[s] in ("possible", "not_mentioned")]
    tremor = symptoms[required]
    if tremor == "absent":
        status = "unmet"
    elif tremor == "present":
        status = "met" if present else ("unknown" if open_ else "unmet")
    else:
        status = "unmet" if not present and not open_ else "unknown"
    pending = ([required] if tremor in ("possible", "not_mentioned") else []) + (open_ if status == "unknown" else [])
    cited = [required, present[0]] if status == "met" else [required, *others]
    return status, [f"symptom:{s}" for s in cited], pending


def _gap(cid: str, kind: str, items: list[str], prompt: str) -> dict[str, Any]:
    return {"criterion": cid, "kind": kind, "items": items, "prompt": prompt}


def evaluate(view: dict[str, Any], report: dict[str, Any], attestations: Any = None) -> dict[str, Any]:
    """The criteria table, the evidence list and the gaps for one scored record.

    ``report`` is the risk report for the same view (its symptom readings and, as context only, its probability and range).
    """
    features.check_view(view)
    answers = check_attestations(attestations)
    wording = policy.wording()
    evidence: dict[str, dict[str, Any]] = {}
    gaps: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    s1, cites1, unreported, labs = _c1(view)
    for e in labs.values():
        evidence[e["id"]] = {key: e[key] for key in ("id", "label", "value", "unit", "text")}
    rows.append({"id": "C1", "text": wording["C1"], "status": s1, "cites": cites1})
    if s1 == "unknown":
        names = [LAB_BY_KEY[k].name for k in unreported]
        gaps.append(_gap("C1", "lab", unreported, "Obtain the result for " + ", ".join(names) + "."))

    symptoms = report["symptoms"]
    for s in SYMPTOM_KEYS:
        label = SYMPTOM_LABEL[s].capitalize()
        evidence[f"symptom:{s}"] = {"id": f"symptom:{s}", "label": label, "value": None, "unit": None,
                                    "text": f"{label} is read as {symptoms[s].replace('_', ' ')} in the note"}
    s2, cites2, pending = _c2(symptoms)
    rows.append({"id": "C2", "text": wording["C2"], "status": s2, "cites": cites2})
    if s2 == "unknown":
        gaps.append(_gap("C2", "symptom", pending, "Document whether the patient has " + ", ".join(SYMPTOM_LABEL[s] for s in pending) + "."))

    for cid in policy.ATTESTED_IDS:
        answer = answers.get(cid)
        status = {"yes": "met", "no": "unmet", None: "unknown"}[answer]
        said = f"The clinician answered {answer} for {cid}" if answer else f"The clinician has not yet answered {cid}"
        evidence[f"attest:{cid}"] = {"id": f"attest:{cid}", "label": f"Clinician answer for {cid}", "value": None, "unit": None,
                                     "text": said}
        cites = [f"attest:{cid}"]
        rows.append({"id": cid, "text": wording[cid], "status": status, "cites": cites})
        if status == "unknown":
            gaps.append(_gap(cid, "attestation", [cid], f"Clinician to answer {cid}: {wording[cid]}"))

    lo, hi = report.get("interval") or (report["probability"], report["probability"])
    evidence["model:risk"] = {"id": "model:risk", "label": "Model estimate", "value": report["probability"], "unit": None,
                              "text": f"The model's estimate is {report['probability']:.0%} (range {lo:.0%} to {hi:.0%}); context only"}
    return {"policy_id": policy.load()["id"], "criteria": rows, "evidence": list(evidence.values()), "gaps": gaps}
