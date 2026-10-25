# Tasks

## 1. Client and configuration

- [x] 1.1 Add an Anthropic API client wrapper that reads the key only from the environment and supports a mock, and verify with a test that a missing key fails clearly and no key string appears in the repo
- [x] 1.2 Add config for model id, prompt version, retry count, caps (full run and pilot), setting rates, matched-pair count and pilot size, make the config reject template styles with the LLM source and LLM settings with template rendering, and verify config tests cover bad values and both rejections

## 2. Settings and plan version 2 (small `data_gen/` code change)

- [x] 2.1 Add per-symptom phrase sets and the four setting profiles, and verify tests that each symptom has at least 3 phrases, no phrase belongs to two symptoms, and every setting has a complete profile
- [x] 2.2 Bump the plan to version 2 with the setting, allowed phrases per symptom, code-computed H/L lab flags and reference ranges, per-setting completeness rules, and stale values for `copy_forward`, and verify tests for determinism, flag correctness at range boundaries, stale rate within 0.03 of config, and that template renderers still pass parse-back on version 2 plans
- [x] 2.3 Add schema version 2 with the optional `pair_group` field and update the validators to accept versions 1 and 2, and verify the committed template dataset still passes `data-gen validate` and that pair records validate

## 3. Verbalizer

- [x] 3.1 Implement per-setting prompts built from the plan only (no label, probability or rule) and verify with a mocked client that prompts contain no ground-truth-only fields and that each setting has its own versioned prompt
- [x] 3.2 Implement verbatim injection insertion via a placeholder marker and verify the exact catalog string appears in the note and that plans without injection yield none
- [x] 3.3 Implement the no-diagnosis, risk or treatment scan (disease name, "diagnos", "risk", "probab", percent signs, common medication names) and verify it flags examples of each and that a mocked violating note is retried

## 4. Validation

- [x] 4.1 Implement tolerant lab parsing (flags, reference ranges, display rounding, dates) with the 1% comparison after unit conversion, and verify tests for flagged, ranged, rounded, converted, invented and wrong values
- [x] 4.2 Implement the independent symptom extraction pass, the allowed-phrase check and plan comparison honoring `note_flag_disagreement` tags, and verify with a mocked client against positive, negated, hedged and missing-phrase cases
- [x] 4.3 Implement bounded retries, exclusion and manifest counting per setting and noise type, and verify a mocked bad note is retried then excluded and counted
- [x] 4.4 Implement the identifier scan on accepted notes and verify it flags SSN-, MRN- and phone-shaped strings and denylisted facility names

## 5. Cache and cost control

- [x] 5.1 Implement the on-disk cache keyed by plan hash, setting, prompt version, model id and sampling seed, and verify a warm-cache rerun makes zero calls and is byte-identical
- [x] 5.2 Implement the full-run and pilot call or spend caps and verify each halts with a clear error leaving the cache intact and no partial record in a split
- [x] 5.3 Implement the `estimate` command counting pilot, matched-pair and extraction calls, and verify it reports uncached call count and estimated cost with zero LLM calls

## 6. Matched-pair groups

- [x] 6.1 Implement matched-pair groups for a configured number of test patients across all four settings with unique setting-hiding record ids and a shared `pair_group`, and verify members share labs, flags, probability and label, have four different settings and distinct texts, and that grouping by `pair_group` deduplicates a pooled metric

## 7. Human quality gates (pilot)

- [ ] 7.1 Generate the capped pilot of 20 notes per setting plus 8 template-fixture controls, write a shuffled blind rating sheet with no setting names and a separate key file, and verify with a test that the sheet contains no setting names and the key maps every note id
- [x] 7.2 Add the gate report that loads the owner's ratings and verifies per-setting plausible rate of at least 0.80 (16 of 20), extractor per-flag accuracy of at least 0.95 on the 80 notes, controls reported separately, and a nonzero exit when any setting fails
- [ ] 7.3 Owner rates the sheet (plausibility and symptom polarities); verify the gate passes for all four settings with the ratings committed, otherwise revise the failing setting's prompt, bump its version, draw 20 fresh notes and re-rate only that setting
- [ ] 7.4 Verify the pilot exclusion rate is at most 15% for every setting, otherwise revise that setting's prompt or the parser before the full run

## 8. Integration

- [ ] 8.1 Run `estimate` at default sizes (about 4,000 train, 1,000 test including 200 matched groups, 420 adversarial) and confirm the estimated cost is acceptable before spending
- [ ] 8.2 Run the real generation under the cap, commit datasets and cache, and verify manifest provenance (source `llm`, model, prompt version, counts per setting, pair groups, exclusions per setting and noise type), that `data-gen validate` passes, and that a second run makes zero calls
- [ ] 8.3 Verify dataset and cache size limits, the identifier and denylist scans and a repository scan for the API key pattern all pass, and state in the dataset README that the template dataset is test fixtures only

## 9. Bounded concurrency (added after the first real pilot; do before group 8)

- [x] 9.1 Add the `concurrency` setting (default 8, 1 to 32, excluded from the config hash) and an ordered parallel runner, and verify tests for in-order results, the worker limit, exception propagation and cancellation of pending work
- [x] 9.2 Make the cache and budget thread-safe with an exact reserved call cap, back off on rate limits without consuming attempts, and run the pilot and full run through the pool, and verify the dataset, counts and pilot sample are identical at 1 and 8 workers, calls overlap, the cap is exact at 8 workers, and backoff behaves as specified
- [x] 9.3 Compact the cache into sorted order after a successful run so the committed file is deterministic, and verify a test that compaction keeps every entry and orders the lines

## 10. Revise the writer after the first LLM review (added after the round-0 review)

Round 0 was rated 5 of 80 plausible by the adversarial reviewer. Its reasons, tallied against the notes: three-to-four significant-figure lab values in 58 of 80 notes, several synonyms for one symptom in 33, "c/o denies" in 14, "fictional study condition" in 5.

- [x] 10.1 Show lab values with three significant figures in the prompt and verify tests of the formatting, its 0.5% bound, and that no prompt value exceeds three significant figures
- [x] 10.2 Reword the prompts (one allowed phrase per symptom, no padding, no "c/o denies", no mention of fiction or a study) and bump `llm.prompt_version` to 2, and verify tests on the prompt text and the version
- [x] 10.3 Add offline checks for repeated symptom wording, contradictory shorthand and meta mentions and verify unit tests including the nested-phrase and same-phrase exceptions
- [ ] 10.4 Pilot round 1 for all four settings with the new prompts and verify the exclusion rate is at most 15% per setting (loosen or reword a check if it is the cause)
- [ ] 10.5 Review round 1 with the adversarial reviewer and then the owner, and verify the gate output; record the plausible rates and what changed in design.md

## 11. Natural variety (added after the web research on how real notes read)

- [x] 11.1 Add polarity-specific wording pools and use them in the plan and the checks, and verify tests that pools are large enough, cross-symptom phrases never overlap, and plans only offer wording for their polarity
- [x] 11.2 Add seeded style traits per setting (fewer for shorthand), record them in the plan, and put them in the prompt as style lines; verify tests of reproducibility, independence from other plan fields, value coverage and the prompt text
- [x] 11.3 Write six original exemplar notes per setting, show two per note chosen by seed, and bump the prompt hash input; verify the exemplars are clean, original, flag-consistent and that the prompt shows exactly two
- [x] 11.4 Reject a note that reproduces eight consecutive words of an exemplar (except stock lines the traits ask for) and verify the check and the stock-line exception
- [x] 11.5 Measure variety (top opener share, distinct trait combinations), report it in the pilot output and key meta, and verify the limits are below the round-0 baseline
- [x] 11.8 Relax the wording rules (hint not requirement, lenient mention detection, per-sentence repetition, exemplar check that ignores numbers and lab names), add a meta-commentary check, fix ratio and reference-range presentation, cap labs and negatives and quotes per note, and verify tests for each
- [x] 11.9 Give the reviewer the glossary of the fictional panel and bump `llm.reviewer_prompt_version` to 2, and verify the glossary lists every lab with its unit and range and contains no scoring or plan data
- [x] 11.10 Tell retries why the previous attempt failed, require the unit for values in the alternate unit, judge flags on the printed value, and give the glossary alternate units, and verify tests of the feedback text, the unit rule, the boundary flag and the glossary
- [ ] 11.6 Pilot round 1 with the revised writer, then verify the variety report and the exclusion rate per setting; adjust a trait, exemplar or check if one is the cause (replaces the pilot in 10.4)
- [ ] 11.7 Review round 1 with the adversarial reviewer (and the owner), and verify the plausible rates and controls gap in the gate output; record what changed in design.md (replaces 10.5)

## Workflow follow-up

- Archive the change after review.
- Verify the archived specs appear under `openspec/specs/llm-note-writing` and that the `clinical-notes` spec carries the updated Note styles requirement.
- Retrain and reevaluate on the LLM notes in the training and evals changes before any published numbers.
