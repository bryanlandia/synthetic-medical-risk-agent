"""Hand-built records and trials, so graders are tested on cases whose right answer is known by construction."""

from types import SimpleNamespace as NS
from typing import Any

from evals.harness import Trial
from evals.report import parse_report

SYMPTOMS = {"tremor": "absent", "fatigue": "present", "photophobia": "not_mentioned", "joint_stiffness": "possible",
            "dizziness": "absent"}
VIEW = {"patient_id": "x", "panel": [{"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}], "note": "Seen."}


def rec(pid="p1", label=0, p=0.2, stated=None, style="shorthand", noise=(), tags=(), pair_group=None, split="test",
        view=None):
    r = NS(patient_id=pid, ground_truth=NS(label=label, true_probability=p), style=style, pair_group=pair_group,
           split=split, plan=NS(symptoms=[NS(flag=f, stated=s) for f, s in (stated or {}).items()]),
           noise=[NS(type=t, lab=l) for t, l in noise],
           tags=[NS(type=t, lab=l, detail=d) for t, l, d in tags])
    r.input_view = lambda: view or {**VIEW, "patient_id": pid}
    r.tag_types = lambda: {t.type for t in r.tags}
    return r


def report(p=0.2, uncertain=False, symptoms=None, warnings=(), labs=(("velorin_index", 104.0, "mg/dL"),),
           evidence=("Labs reviewed.",), disclaimer="This is not medical advice.", **over) -> dict[str, Any]:
    out = {"status": "scored", "probability": p, "uncertain": uncertain, "symptoms": symptoms or dict(SYMPTOMS),
           "data_quality": [{"type": t, "lab": lab} for t, lab in warnings],
           "labs_used": [{"lab": a, "value": v, "unit": u} for a, v, u in labs], "evidence": list(evidence),
           "disclaimer": disclaimer}
    out.update(over)
    return out


def trial(raw: dict[str, Any] | str, record_id="p1", index=0) -> Trial:
    result = parse_report(raw)
    text = raw if isinstance(raw, str) else str(raw)
    return Trial(record_id, "fake@1", index, text, result.report, result.errors)
