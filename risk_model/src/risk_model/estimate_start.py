"""The content file the Estimate a risk page opens on: the lab limits and steps, and one invented borderline patient with its estimate.

The page reads this file for its first view so that it needs no request to show something, and a test keeps the file equal to
what this module builds from the committed model. Regenerate it with
``uv run python -m risk_model.estimate_start ../web/content/estimate.json`` (from ``risk_model/``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import estimate, load, model_hash
from .labs import LABS, SYMPTOM_KEYS

NOTICE = "ALL DATA IS SYNTHETIC. The disease is fictional. This patient is invented."
START_LABS: dict[str, float] = {"velorin_index": 112, "serum_k17": 4.5, "tarnic_acid": 330, "brell_enzyme": 38, "halvin_titer": 4.0,
                                "osmet_level": 292, "plexa_count": 260, "dorrin_ratio": 1.05}
START_SYMPTOMS: dict[str, str] = {"tremor": "possible", "fatigue": "absent", "photophobia": "absent", "joint_stiffness": "absent", "dizziness": "absent"}


def build(directory: Path | str | None = None) -> dict[str, Any]:
    model = load(directory)
    out = model.estimate(START_LABS, START_SYMPTOMS)
    return {
        "notice": NOTICE,
        "model_hash": model_hash(directory),
        "labs": [{"key": lab.key, "name": lab.name, "abbr": lab.abbr, "unit": lab.unit, "min": lab.plaus_lo, "max": lab.plaus_hi,
                  "step": estimate.step(lab.key), "decimals": estimate.DECIMALS[lab.key], "ref_lo": lab.ref_lo, "ref_hi": lab.ref_hi} for lab in LABS],
        "symptoms": list(SYMPTOM_KEYS),
        "start": {"labs": START_LABS, "symptoms": START_SYMPTOMS},
        "estimate": out,
    }


def main(argv: list[str]) -> int:
    text = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if len(argv) > 1:
        Path(argv[1]).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
