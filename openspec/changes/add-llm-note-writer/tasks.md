# Tasks

## 1. Client and configuration

- [ ] 1.1 Add an Anthropic API client wrapper that reads the key only from the environment and supports a mock, and verify with a test that a missing key fails clearly and no key string appears in the repo
- [ ] 1.2 Add config for model id, prompt version, retry count, cap and paraphrase size, and verify config validation tests reject bad values

## 2. Verbalizer

- [ ] 2.1 Implement per-style prompts built from the plan only (no label, probability or rule), and verify with a mocked client that prompts contain no ground-truth-only fields
- [ ] 2.2 Implement verbatim injection insertion via a placeholder marker, and verify the exact catalog string appears in the note and that plans without injection yield none

## 3. Validation

- [ ] 3.1 Implement lab-value parsing and comparison within 1% after unit conversion, and verify tests for matching, converted and mismatching values and tagged noise
- [ ] 3.2 Implement the independent symptom extraction pass and plan comparison honoring `note_flag_disagreement` tags, and verify with a mocked client against positive, negated and hedged cases
- [ ] 3.3 Implement bounded retries, exclusion and manifest counting, and verify a mocked bad note is retried then excluded and counted
- [ ] 3.4 Implement the identifier scan on accepted notes and verify it flags SSN-, MRN- and phone-shaped strings and denylisted facility names

## 4. Cache and cost control

- [ ] 4.1 Implement the on-disk cache keyed by plan hash, prompt version, model id and sampling seed, and verify a warm-cache rerun makes zero calls and is byte-identical
- [ ] 4.2 Implement the call and spend cap and verify it halts with a clear error leaving the cache intact and no partial record in a split
- [ ] 4.3 Implement the `estimate` command and verify it reports uncached call count and estimated cost with zero LLM calls

## 5. Paraphrase groups

- [ ] 5.1 Implement paraphrase groups and verify members share labs, flags, probability and label, carry distinct indexes and have no identical text

## 6. Quality gate

- [ ] 6.1 Hand-check a sample of 100 notes across all four styles, record the labels in the repo, and verify extractor per-flag accuracy is at least 0.95 using a test that reads the sample

## 7. Integration

- [ ] 7.1 Run `estimate` at default sizes (about 4,000 / 1,000 / 400 plus paraphrases) and confirm the estimated cost is acceptable before spending
- [ ] 7.2 Run the real generation under the cap, commit datasets and cache, and verify manifest provenance (source `llm`, model, prompt version, exclusions per style and noise type) and that a second run makes zero calls
- [ ] 7.3 Verify dataset and cache size limits, the identifier scan and a repository scan for the API key pattern all pass

## Workflow follow-up

- Archive the change after review.
- Verify the archived spec appears under `openspec/specs/llm-note-writing`.
- Retrain and reevaluate on the LLM notes in the training and evals changes before any published numbers.
