# Proposal

## Why

The cost-center workflow is the confirmatory scan. An expensive, denial-prone study such as a PET-CT is held up when the packet is incomplete or its evidence is not cited. That delays diagnosis for the patient (Velorin-Kessler Syndrome is often overlooked, and missed it becomes degenerative) and costs the institution rework. A provider-side tool that assembles a cited, honest packet and lists what is still missing helps both. It must never make a record look better than it is, and it must never gate care.

## What Changes

- Add a fictional coverage policy for a K-17 tracer PET-CT as a committed document with six criteria:
  - **From the note and labs, each with a citation:**
    - C1: at least 2 of Velorin index high, Tarnic acid high, Dorrin ratio high, each beyond its reference range in the disease direction. These are the classifier's three strongest labs; the policy quotes no coefficients.
    - C2: tremor present and at least one other symptom present. Possible, hedged or not mentioned is *unknown* with a gap prompt; explicitly absent is *unmet*.
  - **Attested by a clinician in the UI:** C3 symptoms for 6 weeks or more; C4 other explanations considered; C5 no PET-CT or comparable imaging in the last 12 months; C6 specialist evaluation.
  - The model's risk estimate and range (already produced by `evidence-first-chart`) are supporting context ("why this patient was flagged"), never a criterion.
  - A lab is judged on the value converted to its usual unit against the reference range the chart already shows. A lab that is not on the chart makes its criterion input *unknown* and is a gap to obtain.
- Evidence ids are fixed strings built by code from the record: `lab:<key>` for a lab on the chart, `symptom:<key>` for a symptom reading, `attest:<C3..C6>` for an attestation, `model:risk` for the estimate and range. A citation is valid only if its id exists in this packet's evidence list.
- Each criterion is met, unmet or unknown. Unknown becomes a gap to obtain or attest. Nothing is filled in or phrased around.
- Unmet criteria are listed factually, with a clinician-only rationale field to request the scan anyway. The tool never writes that rationale and never decides eligibility.
- The packet is a fixed pipeline with one Claude step, not a tool-calling loop. Code extracts, scores and evaluates the criteria. Claude drafts the evidence summary as structured sentences, each tagged with the criterion and the evidence ids it cites. A verifier rejects the draft if any sentence has no valid citation, contains a number, lab or unit not in its cited evidence, states a status different from the criteria table, or uses banned vocabulary (diagnosis, treatment, urgency, eligibility verdicts such as "qualifies" or "approved"); on failure the template summary is shown and the fallback is counted.
- Each attested item is yes, no or not yet answered: unanswered is *unknown* (a gap) and no is *unmet*. Nothing is pre-filled or inferred from the note, and nothing is stored between requests.
- The clinician presses a clearly labeled demo sign-off, which locks the packet as "drafted by tool, reviewed by clinician (demo)" and offers copy or print, with a banner that all data is synthetic and the disease fictional.
- Attestations come only from structured UI fields filled by a person, never from model-written tool arguments or from note text.
- Add a packet endpoint (`POST /packet`) beside `/analyze`, reached from the web app through a server route that keeps the secret and the service address server-side. It takes the chart's message and the attestation answers, and returns the criteria table, the gap list, the verified summary and its source (`model` or `template`).
- Add code-graded evals: criterion accuracy, gap-detection recall, citation grounding, a measured fabrication rate and verifier fallback rate, and an adversarial set that tries to coax a met criterion or coached wording.

## Capabilities

### New Capabilities
- `scan-readiness`: criteria, per-criterion status with citations, clinician attestation, the verified evidence summary, the packet and its gap list for the PET-CT policy.

### Modified Capabilities
- `agent-service`: a structured packet endpoint beside the chat route, with the existing guards, spend and rate limits.
- `web-demo`: attestation inputs and the packet view.
- `eval-harness`: new graders and a ledger entry; one look at test data.

## Impact

- New policy document; criteria evaluation, gap list and the summary verifier as pure code in `risk_model/` (numpy only, so the agent, the evals and the tests all use the same functions); the one Claude step and the endpoint in `agent/` (independent of `training`, `evals` and `data_gen`); `web/` route and packet view; `evals/` graders and attestation fixtures.
- No data regeneration, retraining or model-hash change. The notes carry only eight labs and symptom flags, so history criteria rely on attestation. A structured history sidecar in `data_gen` is a possible later change. Attestation answers used by evals are seeded fixtures written beside the eval data, not part of the patient record.
- One extra paid Haiku call per packet, under the existing rate limit, input caps and daily spend cap; the packet is a separate call count in usage. No new secret.
- Costs shown for the scan or rework are labeled illustrative and kept out of savings claims.
- Builds on `evidence-first-chart` (archived): its reference ranges and flags in `demo_patients.json`, and the report's `interval` and `gaps`.
- Out of scope: a payer-side view, therapy authorization, history inside synthetic notes, real coverage policies, sliders, multi-turn state, the chat agent's tool arguments.
- Eval categories affected: criterion accuracy, gap recall, citation grounding, no-fabrication, safety (no treatment content, no wording coaching), adversarial.
