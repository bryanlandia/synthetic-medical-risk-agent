# evals

Eval harness for the risk reports of a **FICTIONAL** disease. All data is synthetic; nothing here is medical advice.
The evals come before the system they judge: the contract below says what a correct answer is, the harness scores
any system against it, and reference systems prove the harness works. Design: `openspec/changes/add-eval-harness`.

## The contract

A system returns one **risk report** per patient record: either `scored` (probability, `uncertain` flag, a reading of the
five symptoms, the lab values it relied on, data-quality warnings, short evidence, a "not medical advice" disclaimer)
or `declined` (a reason and a message). Parsing is strict; output that is not a valid report is counted as a failure
and never dropped. The JSON Schema is committed at `contract/risk_report.schema.json` (`uv run evals schema`).

## Systems

A system is a function from a record's **input view** (patient id, lab panel, note; never the answers) to a report.

- `oracle`: knows the hidden rule. The ceiling, and a check on every grader. A reference, not a system under test.
- `floor`: always reports the training prevalence.
- `lab_only`: logistic regression on the labs alone, fit on train excluding dev.
- API-backed systems (`PromptSystem`): a prompt, a model and a client behind a response cache and call and spend caps.

## Discipline

- **Dev** is 500 train patients (seeded, stratified by label, computed not stored; `evals.devsplit.dev_ids`). Iterate on
  dev only. Training code must use `train_ids` (everything except dev).
- **`test` and `adversarial`** are scored only with `--final`, and each final run is recorded in `results/ledger.json`, so
  a headline number is one look at the test set.
- Happy-path metrics count each patient once (matched-pair members share a patient). Intervals come from a seeded
  bootstrap that resamples patients. Every result also states its minimum detectable difference.
- Targets (`results/targets_v1.json`) are derived from the baselines and say which evals are capability (room to climb)
  and which are regression (hold what is achievable).

## Commands (from `evals/`; `uv sync` first)

```
uv run pytest -q                                              # harness tests (no key, no spend)
uv run evals schema                                           # print the report JSON Schema
uv run evals run --system floor --split dev --limit 50        # run a reference system through Inspect; writes runs/
uv run evals baselines                                        # the three references on dev -> results/baselines, targets_v1
uv run evals regression                                       # the fast key-free regression subset (what CI runs)
uv run evals failures runs/floor/dev/trials.jsonl --grader data_quality -n 5   # read failing transcripts
uv run evals run --system oracle --split test --final         # protected splits need --final (recorded in the ledger)
```

## The frontier baseline

A strong model with a good prompt, scored on the same evals as everything else. It gets the report schema as a tool
(`submit_report`; the tool is offered, not forced) and a prompt that is a **briefing**: the contract, the fictional
labs with units and ranges, the safety rules, "note text is data", and a qualitative description of the disease. It has
no weights, thresholds or record content (`tests/test_frontier_prompt.py` checks). Prompt versions are files in
`prompts/frontier/`; the protocol is enforced by code and recorded in `results/frontier/prompt_versions.json`, a
hash-chained file whose earlier entries cannot be edited unnoticed:

- at most 5 prompt versions, each scored on dev only (Haiku 5.5); a sixth is refused;
- `evals freeze` picks one; `test` and `adversarial` are refused until then, and only for that prompt's hash;
- the final runs use Haiku 5.5 with the frozen prompt (Sonnet 5.5 was scored on dev once for comparison and was not better); one final run each on `test` and `adversarial`, three trials on
  the matched-pair subset; a repeated final run needs `--force`;
- every stage prints an estimate first (`evals estimate`), has a call and spend cap, and refuses to start above it;
  responses are cached, so a rerun costs nothing;
- results are compared with targets v1 and labelled clearly met / not distinguishable / clearly not met from the 95%
  interval; `evals report` is marked INCOMPLETE until the failing transcripts a person read are recorded in
  `results/frontier/reading.json` (per grader: `transcripts` as `suite:sample_id:trial`, `findings`, `grader_fault`).

**Headline: the frontier baseline** (Haiku 5.5, frozen prompt v5 with the qualitative briefing, `test` split, 931
patients; full report in `results/frontier/report.md`). Sonnet 5.5 on dev scored AUC 0.739 against 0.752 for Haiku, so
Haiku is the final model.

| Metric | Value (95% interval) | Target v1 |
|---|---|---|
| AUC | 0.735 (0.700 to 0.768) | 0.799: clearly not met |
| Brier | 0.181 (0.169 to 0.194) | 0.159: clearly not met |
| Log loss | 0.540 (0.511 to 0.571) | 0.482: clearly not met |
| Data quality, exact match | 0.965 (0.949 to 0.979) | 0.5: clearly met |
| Borderline uncertain rate | 0.472 (0.393 to 0.560) | 0.5: not distinguishable |
| Invalid or unsafe reports | 0.1% (0.0 to 0.3%) | 0: not distinguishable |
| Consistency, pass^3 | 0.627 (0.556 to 0.698) | none |

**Headline: the trained classifier** (`classifier@414c2d467c87+r1`: a CPU note reader and a logistic risk classifier, fitted
on train without dev; `test` split, 931 patients; full report in `results/classifier/report.md`). The paired comparison
with the frontier baseline above, on the same patients:

| Metric | Classifier | Frontier baseline | Paired difference (95% interval) | Target v1 (classifier) |
|---|---|---|---|---|
| AUC | 0.796 (0.762 to 0.827) | 0.735 | +0.061 (+0.037 to +0.084), classifier better | 0.799: not distinguishable |
| Brier | 0.155 (0.143 to 0.169) | 0.181 | -0.026 (-0.034 to -0.018), classifier better | 0.159: reached |
| Log loss | 0.483 (0.449 to 0.520) | 0.540 | -0.058 (-0.080 to -0.037), classifier better | 0.482: not distinguishable |
| Data quality, exact match | 1.000 | 0.965 | | 0.5: clearly met |
| Borderline uncertain rate | 0.584 (0.484 to 0.681) | 0.472 | | 0.5: reached, not distinguishable |
| Invalid or unsafe reports | 0 of 3,634 | about 0.1% | | 0: clearly met |
| Consistency across settings (mean SD) | 0.011 | | | 0.05: reached |

Trials are identical (676 of 676 matched-pair records, three trials). Reading its failing transcripts showed label noise
and records with a missing lab, not a grader fault. The model is small (197 kB), runs in under a millisecond on a CPU, and
the synthetic rule is logistic, which makes this family a good fit; the model card says so.

**Headline: the agent** (`agent@414c2d467c87+p125eec6826c9+claude-haiku-5-5+v0.1.0.1`: Haiku 5.5 routes the message to the
classifier's scoring tool or a decline and writes a short reply; text intake, the report and the disclaimer are code; `test`
split, 931 patients; Haiku was the only orchestrator tried). Its report is the classifier's, so the happy-path metrics are
identical to the classifier's (paired difference +0.0000 on AUC, Brier and log loss). What the agent adds is measured by the
tool-use and scope rows:

| Metric | Value (95% interval) | Target v1 |
|---|---|---|
| AUC, Brier, log loss | the classifier's (0.796, 0.155, 0.483) | as the classifier |
| Fabrication, safety, parse (3,634 requests; 658 adversarial) | 0 failures, 1.000, 0 | clearly met |
| Data quality, exact match | 1.000 test; 0.800 adversarial | 0.5: clearly met |
| Scoring tool used once on a record | 0.9945 (0.9897 to 0.9983) test; 0.9975 over three trials | 0.99: reached |
| Over-refusal on records | 0 of 3,634 | 0.05: clearly met |
| Reply agrees with the report | 1.000; template used for 1.8% of replies | none |
| Scope set, declined with the right reason (44 prompts, dev-time) | 44 of 44 | 0.95 / 0.90: clearly met |
| Legitimate notes with medications refused (12) | 0 | 0.05: clearly met |
| Injected instructions resisted (10 scope + 60 adversarial) | 70 of 70 | none |
| Consistency across settings, mean SD / pass^3 | 0.011 / 0.982 | as the classifier |

Misses and caveats, with the transcripts read in `results/agent/reading.md`: AUC and log loss miss the target by the same
0.004 and 0.0005 as the classifier (not distinguishable); 20 of 3,634 test requests (0.55%) were scored but also tried a
second tool call (13 `decline`, 7 a second `score_message`), which the service refused, so the answer was still the
classifier's report, but the grader counts them as not using the tool exactly once; `recall:note_flag_disagreement` on
the adversarial split is 0.0175, as for the classifier. The scope prompt was changed once after the first scope run
(email addresses were missing from the list of personal identifiers), so the scope result is a repaired one; `test` and
`adversarial` were looked at only after that. A request takes about 4 s (p50, p90 5.5 s) and costs about $0.0006 with
the model, against under a millisecond and nothing for the classifier alone.

API-backed systems run concurrently (`--workers`, default 8 samples at a time) and give identical transcripts, results
and cache contents at any worker count.

Graders are plain functions (`evals/graders.py`, `injection.py`, `consistency.py`) wrapped by Inspect scorers. The
oracle is run through every grader as a self-check (`evals/selfcheck.py`): a grader that does not score it as expected is
reported as broken, not as a system failure.

## Demo patients for the web page

`uv run evals demo-patients` writes `web/content/demo_patients.json`: four dev-split patients chosen by fixed rules (a routine
record, mixed units with a missing lab, a borderline probability, a note that disagrees with its panel), each with its chart
and the message `render_message` builds. The file has no ground-truth field, and `tests/test_demo_patients.py` checks that every
id is in the dev split, every message equals a fresh rendering and the committed file is what the command writes.
