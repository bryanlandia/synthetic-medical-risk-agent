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
- the final model (Sonnet 5.5) gets the same prompt; one final run each on `test` and `adversarial`, three trials on
  the matched-pair subset, and a dev run for comparison; a repeated final run needs `--force`;
- every stage prints an estimate first (`evals estimate`), has a call and spend cap, and refuses to start above it;
  responses are cached, so a rerun costs nothing;
- results are compared with targets v1 and labelled clearly met / not distinguishable / clearly not met from the 95%
  interval; `evals report` is marked INCOMPLETE until the failing transcripts a person read are recorded in
  `results/frontier/reading.json` (per grader: `transcripts` as `suite:sample_id:trial`, `findings`, `grader_fault`).

API-backed systems run concurrently (`--workers`, default 8 samples at a time) and give identical transcripts, results
and cache contents at any worker count.

Graders are plain functions (`evals/graders.py`, `injection.py`, `consistency.py`) wrapped by Inspect scorers. The
oracle is run through every grader as a self-check (`evals/selfcheck.py`): a grader that does not score it as expected is
reported as broken, not as a system failure.
