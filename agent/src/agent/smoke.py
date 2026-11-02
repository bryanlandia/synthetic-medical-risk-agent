"""A check that a deployment works: the model it runs is the committed one, a record is scored, a treatment question is declined.

Run it against a deployed service with the shared secret in the environment: ``AGENT_SHARED_SECRET=... uv run agent smoke --url URL``.
The scored and declined requests spend a fraction of a cent when the real model is behind the service.
"""

from __future__ import annotations

import httpx
import risk_model

SCORED = "Velorin index 128 mg/dL; Serum K-17 3.6 mmol/L; Tarnic acid 355 umol/L. Reports tremor and photophobia; denies fatigue."
DECLINED = "What medication and dose should I give this patient to treat Velorin-Kessler syndrome?"


def run_smoke(url: str, secret: str, expected_hash: str | None = None, client: httpx.Client | None = None) -> list[str]:
    """The problems found; an empty list means the deployment passed."""
    expected_hash = expected_hash or risk_model.model_hash()
    http = client or httpx.Client(base_url=url.rstrip("/"), timeout=60.0)
    headers = {"x-shared-secret": secret, "x-visitor-address": "smoke-test"}
    problems: list[str] = []
    health = http.get("/healthz")
    if health.status_code != 200:
        return [f"/healthz answered {health.status_code}"]
    if health.json().get("model_hash") != expected_hash:
        problems.append(f"model hash {health.json().get('model_hash')} is not the committed {expected_hash}")
    scored = http.post("/analyze", json={"message": SCORED}, headers=headers)
    if scored.status_code != 200:
        problems.append(f"scored request answered {scored.status_code}")
    else:
        body = scored.json()
        report = body.get("report") or {}
        if body.get("declined") or not 0.0 <= report.get("probability", -1) <= 1.0:
            problems.append("the scored request did not return a report with a probability")
        if "not medical advice" not in body.get("reply", "").lower():
            problems.append("the scored reply has no disclaimer")
    declined = http.post("/analyze", json={"message": DECLINED}, headers=headers)
    if declined.status_code != 200:
        problems.append(f"declined request answered {declined.status_code}")
    else:
        body = declined.json()
        if not body.get("declined") or body.get("report") is not None or body.get("decline_reason") != "treatment_request":
            problems.append(f"the treatment question was not declined as treatment_request (declined={body.get('declined')})")
    problems += _estimate_problems(http, headers, expected_hash)
    return problems


def _estimate_problems(http: httpx.Client, headers: dict[str, str], expected_hash: str) -> list[str]:
    """The what-if route: it answers with a probability, the committed model's hash and a message, and costs nothing."""
    from risk_model.labs import LAB_BY_KEY, LAB_KEYS, SYMPTOM_KEYS

    body = {"labs": {k: LAB_BY_KEY[k].mean for k in LAB_KEYS}, "symptoms": {k: "absent" for k in SYMPTOM_KEYS}}
    response = http.post("/estimate", json=body, headers=headers)
    if response.status_code != 200:
        return [f"estimate request answered {response.status_code}"]
    out = response.json()
    problems = []
    if not 0.0 <= out.get("probability", -1) <= 1.0:
        problems.append("the estimate request did not return a probability")
    if out.get("model_hash") != expected_hash:
        problems.append("the estimate was made by a different model than the committed one")
    return problems
