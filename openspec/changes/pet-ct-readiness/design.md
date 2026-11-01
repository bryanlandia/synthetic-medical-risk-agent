# Design

## Context

See proposal.md for motivation. `evidence-first-chart` is archived and gives this change its inputs: `risk_model/report.build` returns the probability, `interval`, `gaps`, the five symptom readings and `labs_used`; `risk_model/labs.py` holds each lab's reference range and unit conversion; `web/content/demo_patients.json` already carries per-lab range and H/L flag, computed after unit conversion by `evals demo-patients`. The agent (`agent/src/agent/app.py`) applies the secret, size cap, rate limit and spend cap in front of `/analyze`, and its reply check lives in the agent. The web app reaches the agent only through `web/app/api/analyze/route.ts` and `web/lib/forward.ts`, which whitelist response fields. `agent/` may depend on `risk_model` only.

## Goals / Non-Goals

**Goals:** a packet whose every status and citation is computed by code and checkable, one narrow model step whose output cannot reach the user unless a verifier passes it, and evals that measure how often the model step fails.

**Non-Goals:** a payer-side view; any eligibility verdict or advice; history in the synthetic notes or a `data_gen` sidecar; real policies; editing recorded values; multi-turn state; changing the model, its hash or training.

## Decisions

- **Criteria, evidence ids, gaps and the verifier are pure functions in `risk_model/`.** Numpy-only code with no model call, so the agent, the evals (which already import `risk_model` for reference computations) and unit tests share one implementation. The eval reference for criterion accuracy is still written separately, in `evals/`, from the raw panel and plan, so a bug in the shared code is not graded by itself. Alternative: put it in `agent/`, which the evals cannot import.
- **A fixed pipeline, not an agent loop.** `/packet` runs: guards, text intake and report (same code as `/analyze`), criteria and gaps, one no-tool Haiku call for the summary, verifier, response. No tool-calling means the model cannot choose what is scored or set a status. Alternative: reuse the Strands agent with a packet tool, which adds a decline-routing turn and tool-argument surface this feature does not need; the existing guard still runs first so declines behave the same.
- **Policy as data.** The six criteria, their wording and the lab/direction list live in one committed policy file (markdown plus a small JSON of structured fields) read by the code and shown by the page; a test fails if the page's text and the file differ. The "disease direction" for C1 is stated per lab as above-range for all three and quotes no coefficient.
- **Three-valued logic is explicit.** C1 counts high labs `h`, unreported labs `u` among the three; met if `h >= 2`, unmet if `h + u < 2`, else unknown. C2 is the same over the other four symptoms with tremor required. Possible and not_mentioned count as unreported-style unknowns, absent as decided-no. Impossible values are treated as unreported, matching how the report treats them.
- **Attestation is a closed request field.** `attestations` is an object with optional keys C3 to C6 and values yes/no; pydantic forbids extras. Unanswered is the absence of the key, so there is no default that could say yes. The clinician rationale never leaves the browser except as printed text: it is not sent to the service, so the model cannot see it and the service cannot echo or log it.
- **Summary format and verifier.** The model returns JSON: a list of `{criterion, status, text, cites[]}`. The verifier is deterministic: every cite must be in the evidence list; every number token and unit in `text` must appear in the cited evidence strings (compared at the written precision); `status` must equal the table; `text` is scanned against the denylist plus banned verdict and coaching words. Any failure rejects the whole draft, the template summary is built from the table, and the reason code is counted. Alternative: repair a sentence, which would hide the failure rate that the evals are meant to measure.
- **Raw drafts are measured through the verifier's reason codes.** The evals never import the agent, so they cannot call the summarizer themselves. The service returns the shown summary plus the verifier's reason classes (`number`, `unit`, `lab`, `bad_citation`, `no_citation`, `status`, `banned`, `shape`, `model_failed`; never the draft's text) when it fell back to the template. The raw fabrication rate is the share of packets whose classes include `number`, `unit`, `lab` or `bad_citation`; the fallback rate is the share served from the template. The log keeps the same classes, not text.
- **Reproducibility.** Attestation fixtures are generated from a fixed seed over the dev, test and adversarial ids with equal shares of yes, no and unanswered per criterion, and are committed. Pinned prompt text has a hash like the agent's, reported by `/healthz` as `packet_prompt_hash`. Haiku calls are cached in the eval runner by the existing cache, so a rerun costs nothing.
- **Cost and secrets.** One extra Haiku call per packet with a small output cap, counted in usage and the daily total; no new secret or variable. The packet route in `web/` reads the same two server variables. Cost figures, if shown, are fixed illustrative constants in the policy file, labelled fictional.
- **Versioning.** The packet logic gets its own version string; the classifier hash and `LOGIC_VERSION` stay unchanged. The ledger entry is under the agent system's version with a `packet` stage so earlier entries stay valid.

## Risks / Trade-offs

- [Criteria that are too easy make the accuracy target meaningless] → the fixtures cover every status for every criterion, and the grader reports per-criterion counts of each true status.
- [The verifier's number match is too strict and everything falls back] → measure the fallback rate on dev with Haiku first; the fixed template summary is a complete answer, so a high rate lowers polish, not correctness. Tune the prompt on dev only, with a version cap like the frontier baseline.
- [The verifier misses a paraphrased verdict] → ban list plus a requirement that every sentence is tagged with a criterion and status the table confirms; the adversarial set includes paraphrases, and any miss found is added to the list before the one look at test.
- [A reader takes a packet as a coverage decision] → no verdict words, the demo sign-off label and the fictional-policy notice on every view, enforced by tests.
- [The rationale stays only in the browser] → it does not survive a reload, and the demo says so; this is accepted to keep free text out of the service.

## Open Questions

None that change what is built. Assumed: the model summary uses Haiku 5.5 like the agent, and the policy's illustrative cost constants are optional and may be omitted.
