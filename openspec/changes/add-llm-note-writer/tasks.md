# Tasks

## 1. Client and configuration

- [ ] 1.1 Add an Anthropic API client wrapper that reads the key only from the environment and supports a mock, and verify with a test that a missing key fails clearly and no key string appears in the repo
- [ ] 1.2 Add config for model id, prompt version, retry count, caps (full run and pilot), setting rates, matched-pair count and pilot size, make the config reject template styles with the LLM source and LLM settings with template rendering, and verify config tests cover bad values and both rejections

## 2. Settings and plan version 2 (small `data_gen/` code change)

- [ ] 2.1 Add per-symptom phrase sets and the four setting profiles, and verify tests that each symptom has at least 3 phrases, no phrase belongs to two symptoms, and every setting has a complete profile
- [ ] 2.2 Bump the plan to version 2 with the setting, allowed phrases per symptom, code-computed H/L lab flags and reference ranges, per-setting completeness rules, and stale values for `copy_forward`, and verify tests for determinism, flag correctness at range boundaries, stale rate within 0.03 of config, and that template renderers still pass parse-back on version 2 plans
- [ ] 2.3 Add schema version 2 with the optional `pair_group` field and update the validators to accept versions 1 and 2, and verify the committed template dataset still passes `data-gen validate` and that pair records validate

## 3. Verbalizer

- [ ] 3.1 Implement per-setting prompts built from the plan only (no label, probability or rule) and verify with a mocked client that prompts contain no ground-truth-only fields and that each setting has its own versioned prompt
- [ ] 3.2 Implement verbatim injection insertion via a placeholder marker and verify the exact catalog string appears in the note and that plans without injection yield none
- [ ] 3.3 Implement the no-diagnosis, risk or treatment scan (disease name, "diagnos", "risk", "probab", percent signs, common medication names) and verify it flags examples of each and that a mocked violating note is retried

## 4. Validation

- [ ] 4.1 Implement tolerant lab parsing (flags, reference ranges, display rounding, dates) with the 1% comparison after unit conversion, and verify tests for flagged, ranged, rounded, converted, invented and wrong values
- [ ] 4.2 Implement the independent symptom extraction pass, the allowed-phrase check and plan comparison honoring `note_flag_disagreement` tags, and verify with a mocked client against positive, negated, hedged and missing-phrase cases
- [ ] 4.3 Implement bounded retries, exclusion and manifest counting per setting and noise type, and verify a mocked bad note is retried then excluded and counted
- [ ] 4.4 Implement the identifier scan on accepted notes and verify it flags SSN-, MRN- and phone-shaped strings and denylisted facility names

## 5. Cache and cost control

- [ ] 5.1 Implement the on-disk cache keyed by plan hash, setting, prompt version, model id and sampling seed, and verify a warm-cache rerun makes zero calls and is byte-identical
- [ ] 5.2 Implement the full-run and pilot call or spend caps and verify each halts with a clear error leaving the cache intact and no partial record in a split
- [ ] 5.3 Implement the `estimate` command counting pilot, matched-pair and extraction calls, and verify it reports uncached call count and estimated cost with zero LLM calls

## 6. Matched-pair groups

- [ ] 6.1 Implement matched-pair groups for a configured number of test patients across all four settings with unique setting-hiding record ids and a shared `pair_group`, and verify members share labs, flags, probability and label, have four different settings and distinct texts, and that grouping by `pair_group` deduplicates a pooled metric

## 7. Human quality gates (pilot)

- [ ] 7.1 Generate the capped pilot of 20 notes per setting plus 8 template-fixture controls, write a shuffled blind rating sheet with no setting names and a separate key file, and verify with a test that the sheet contains no setting names and the key maps every note id
- [ ] 7.2 Add the gate report that loads the owner's ratings and verifies per-setting plausible rate of at least 0.80 (16 of 20), extractor per-flag accuracy of at least 0.95 on the 80 notes, controls reported separately, and a nonzero exit when any setting fails
- [ ] 7.3 Owner rates the sheet (plausibility and symptom polarities); verify the gate passes for all four settings with the ratings committed, otherwise revise the failing setting's prompt, bump its version, draw 20 fresh notes and re-rate only that setting
- [ ] 7.4 Verify the pilot exclusion rate is at most 15% for every setting, otherwise revise that setting's prompt or the parser before the full run

## 8. Integration

- [ ] 8.1 Run `estimate` at default sizes (about 4,000 train, 1,000 test including 200 matched groups, 420 adversarial) and confirm the estimated cost is acceptable before spending
- [ ] 8.2 Run the real generation under the cap, commit datasets and cache, and verify manifest provenance (source `llm`, model, prompt version, counts per setting, pair groups, exclusions per setting and noise type), that `data-gen validate` passes, and that a second run makes zero calls
- [ ] 8.3 Verify dataset and cache size limits, the identifier and denylist scans and a repository scan for the API key pattern all pass, and state in the dataset README that the template dataset is test fixtures only

## Workflow follow-up

- Archive the change after review.
- Verify the archived specs appear under `openspec/specs/llm-note-writing` and that the `clinical-notes` spec carries the updated Note styles requirement.
- Retrain and reevaluate on the LLM notes in the training and evals changes before any published numbers.
