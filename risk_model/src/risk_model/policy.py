"""The fictional PET-CT coverage policy, loaded from the committed JSON. The wording here is the only wording of the criteria."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

POLICY_DIR = Path(__file__).parent / "policy"
CRITERIA_IDS = ("C1", "C2", "C3", "C4", "C5", "C6")
ATTESTED_IDS = ("C3", "C4", "C5", "C6")


@cache
def load() -> dict[str, Any]:
    policy = json.loads((POLICY_DIR / "pet_ct_k17.json").read_text())
    if tuple(c["id"] for c in policy["criteria"]) != CRITERIA_IDS:
        raise ValueError("the policy must define exactly C1 to C6, in order")
    return policy


def wording() -> dict[str, str]:
    return {c["id"]: c["text"] for c in load()["criteria"]}
