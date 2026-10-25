# Design

## Context

Builds on the archived `add-synthetic-data-generator`, which provides the record schema, splits, ground truth and a versioned note plan (version 1) with template renderers. This change plugs an LLM verbalizer into the plan-to-text seam and extends the plan additively. See proposal.md for motivation and the specs for requirements. The repo is public, so the API key lives only in the environment.

The template notes were reviewed and found unrealistic: five fixed symptom phrases, a few boilerplate frames, four-significant-figure lab values, no lab flags or reference ranges, and no variety of setting. They remain as test fixtures.

## Goals / Non-Goals

**Goals:**
- Notes that plausibly resemble four clinician-authored documentation settings, with the plan's ground truth and noise labels intact.
- Every accepted note verifiably faithful, with measured validator quality and a human plausibility gate.
- Data that supports per-setting breakdowns, held-out-setting experiments and same-patient comparisons across settings.
- Reruns free and spend bounded, so the repo reproduces without an API key.

**Non-Goals:**
- Making models look good. The project's deliverable is a sound evaluation; modest or null results are acceptable. The data should be honest about its difficulty (Bayes ceiling stays in the manifest), not tuned for headroom.
- Patient-authored text, clinician diagnoses or treatment statements.
- Bit-reproducible LLM output (we cache and commit it instead).
- Clinical validation of realism. The gate measures plausibility to the project owner, who is not claimed to be a clinician.
- Running the held-out-setting experiments (training and evals changes).

## Decisions

**Four settings as profiles.** Each setting is a versioned prompt plus a rule set in the plan.

| Setting | Form | Plan rules |
|---|---|---|
| `shorthand` | brief, abbreviations, headline items only | 2 to 3 labs, at most 2 negatives |
| `ehr_template` | ROS grouped by body system, labs with H/L flags and reference ranges, typed history and a monitoring plan | all non-missing labs, flags from code |
| `ai_scribe` | narrative prose, may quote the patient, hedged phrasing | 0 to 3 labs inline, hedges favored |
| `copy_forward` | progress note carrying prior-visit text | elevated stale-value rate, stale values tagged |

These come from general knowledge of documentation styles and are plausible stand-ins, not a verified catalog.

**Plan version 2 (additive).** Adds the `setting`; a per-symptom allowed phrase set (synonyms such as shaky, tired, lightheaded, light sensitivity, stiff joints, chosen deterministically by seed) so wording varies and the extractor can check it; lab flags (H, L or none) computed by code from the stated value against the lab's reference range, so the LLM never decides them; and stale-value rules that now also cover `copy_forward`. Template renderers ignore the new fields, and the committed version 1 dataset still validates. Alternative: let the LLM choose wording freely, rejected because the extractor and the diversity check need a controlled vocabulary.

**Schema version 2 (additive).** Optional `pair_group` on a record. Matched-pair records use `patient_id` of the form `<base>-m<k>` with `k` randomly assigned per group so the id does not reveal the setting. Validators accept schema versions 1 and 2.

**Matched pairs are a subset of the test split** (default 200 patients, so 800 records). Alternative: a separate fourth split, rejected because it would change the split requirements of the archived `synthetic-cohort` spec. Cost: pooled metrics must deduplicate by `pair_group`, which the spec requires to be possible.

**No clinician impression.** Real notes often contain an assessment, which is a noisy label proxy and would let a classifier read the clinician's guess instead of the symptoms. Notes may contain only plan-and-monitoring language naming no disease or drug, enforced by a denylist scan (disease name, "diagnos", "risk", "probab", percent signs, common medication names). This is the first call and can be revisited as a separate, deliberate experiment.

**Anthropic API with a Haiku-class model, model id in config.** Cheap and fast for thousands of short notes. Alternative: a larger model, rejected for cost; the model id is recorded in the manifest.

**Prompt per setting, built from the plan only.** The prompt receives the plan facts (labs with units, flags and ranges; symptoms with polarity, hedge and allowed phrases; noise instructions) and the setting profile, never the label, true probability or scoring rule. Injection text is inserted by code after generation, not authored by the model.

**Tolerant lab parsing plus an independent symptom extractor.** Lab values are parsed by code that tolerates flags, reference ranges, dates and display rounding, compared within 1% after unit conversion. Symptom polarity comes from a separate extraction prompt over the controlled vocabulary. Alternative: trust the writer's own claims, rejected because it shares the writer's errors. A pilot exclusion rate above 15% for a setting means its prompt or parser needs work before the full run.

**Human gate on one sheet.** The pilot generates 20 notes per setting (80), plus 8 template-fixture control notes, shuffled, with no setting names, and a separate key file. For each note the owner records plausibility (yes or no) and the polarity of each of the five symptoms. One pass produces both gates: at least 16 of 20 plausible per setting, and at least 0.95 per-flag extractor accuracy on the 80 notes. The controls are reported, not gated, and show whether the rater discriminates. A failing setting gets a revised prompt, a bumped version, 20 fresh notes and a re-rating of that setting only. Ratings are committed. Alternative: automated plausibility scoring by an LLM judge, rejected as the primary gate because it would share the writer's blind spots; it could be added as a cheap secondary signal later.

**Bounded concurrency with ordered consumption.** The first real pilot made about one call every 2.7 s, so the full run (about 12,000 first-attempt calls) would take roughly 10 hours sequentially. Notes are independent, so a thread pool (default 8, at most 32) runs them in parallel while results are consumed strictly in plan order. Dataset assembly, counts, the early-stop decisions and the sample all use that ordered prefix, so output is identical at any worker count; notes still in flight when a run stops finish and are cached, which is not waste because every pilot and full-run note is a real dataset item. The call cap is reserved before each paid call, so it is exact; the spend cap can overshoot by at most the in-flight calls (a few hundredths of a dollar). A 429 or overload is retried with exponential backoff and jitter without consuming the note attempt. Alternatives: asyncio (more rewrite for no gain on I/O-bound calls) and the Batch API (50% cheaper but asynchronous, which would complicate the retry-and-validate loop; worth revisiting only if cost, not time, becomes the problem). The worker count is excluded from the config hash because it cannot change the data.

**Bounded retries, then exclude.** Up to a configured number of attempts per note; failures are excluded and counted, with rates reported per setting and noise type so selection bias is visible.

**Cache keyed by plan hash, setting, prompt version, model id and sampling seed,** committed with the datasets so a fresh clone reruns with zero calls.

**Cost control.** A hard `--max-llm-calls` cap, a small separate cap for the pilot, a dry-run `estimate` that counts uncached calls, and a Console spend limit. Budget: the dry-run `estimate` projects about 6,000 notes (train 4,000, test 1,000 including 200 matched groups written four times, adversarial 420) plus extraction calls and expected retries at roughly $3 for the full run and $0.04 for the 80-note pilot, using assumed token counts (Haiku 5.5 is priced at $0.10 / $0.50 per million tokens). The pilot replaces the assumptions with measurements. Default caps are generous safety nets (25,000 calls, $15 for the full run; 600 calls, $1 for the pilot).

**Statistical power is part of the design.** With about 1,000 test notes over four settings there are roughly 250 per setting, enough for rough per-setting estimates (a rough AUC uncertainty near ±0.04) but not fine comparisons. The evals should report confidence intervals; enlarging the test split is a config change if finer slices are wanted.

### Variety comes from the inputs, not from the model (added after the round-0 review)

The review's complaint was uniformity: the same layout and openers on every note of a setting (round 0: 100% of copy_forward notes opened "Patient seen in", 70% of ehr_template, 40% of ai_scribe). These models take no temperature or sampling settings, so asking the model to "vary" cannot be relied on. Three levers, all seeded and recorded:

1. **Polarity-specific wording pools.** Each symptom has six or more phrases for present, hedged and denied. Negating a positive pool produced "feels not exhausted, no low energy". The plan offers two or three candidates and the writer uses one.
2. **Style traits** (`traits.py`): per note, a few habits drawn from the render seed (heading style, section order, how labs and negatives are laid out, how the note opens and closes), turned into "style lines" in the prompt. Shorthand has four traits, the documented settings five or six. The draw uses its own stream, so no other plan field moves. The traits live in the plan, so evals can slice or hold out by them.
3. **Exemplars**: six original fictional notes per setting, written from features observed in public sample notes and abbreviation guides (grouped negatives, trend phrasing, stock "reviewed, no changes" lines, terse fragments, numbered plans, either skeletal or verbose AI-scribe summaries), not copied from them. Each note is shown two of the six, chosen by seed, with an instruction to match register and rhythm only. The copy risk is mitigated by showing few, by a code check that rejects eight consecutive words from any exemplar, and by the exemplars being fictional with this project's lab panel.

Variety is measured in code (top opener share, distinct trait combinations) and reported by the pilot, in addition to the reviewer's verdict. The pilot's per-setting limits were set below the round-0 baseline. Alternatives rejected: asking the model for "variety" in the prompt (unreliable without sampling control), and scraping real notes (private, and licensing).

Cost: the exemplars add about 400 input tokens per writer call (a few cents per pilot).

### What round 1 taught (added after the second review)

Round 1 (variety levers on) rose from 5 to 18 of 51 accepted notes rated plausible (ehr_template 7/20, copy_forward 10/20), but my own new checks rejected 20 to 62% of the writer's notes (repeated wording 103, missing phrase 40, copied exemplar 39), leaving ai_scribe and shorthand with only 8 and 3 accepted notes. Reading the rejected text showed three mistakes of mine:

- **Rigid wording rules caused the stilted text.** "Use exactly one of these phrases" made the model contort ("Negative for denies fatigue", "not woozy at all") and, for shorthand, print its own reasoning ("Wait, that breaks the rule..."). Wording is now a vocabulary hint; mention detection is lenient; polarity stays with the independent extractor. Repetition is flagged only inside one sentence or at three wordings, and reasoning leaking into the output is its own failure code.
- **The exemplar-copy check fired on result blocks** that merely share a layout with an exemplar. Numbers and lab names now break a run.
- **Uniformity came from the profile.** ehr_template listed all eight labs in a uniform block, and several settings stated every symptom, one positive and four negatives. ehr_template now states at most six labs, ehr_template and copy_forward at most three negatives, and ai_scribe at most one patient quote.

The reviewer's remaining reasons were mostly about presentation: a unit repeated inside the reference range ("(ref 0.6-1.4 ratio)"), "ratio" as a unit, and invented analytes. The first two are fixed in the prompt; for the third the reviewer (prompt version 2) is now given the glossary of the fictional panel and told not to count it against a note. Stock phrases in the polarity pools that read stilted in prose ("not tired", "not woozy") were replaced.

### What round 2 taught

Round 2 (writer fixes, fictional-panel glossary for the reviewer): direct review rated shorthand 19/20, copy_forward 15/20, ehr_template 13/20 and ai_scribe 6/20 plausible (66% overall, up from 5/80 and then 18/51), with the browser run on 15 notes agreeing. Exclusions were still 23 to 31%, nearly all `symptom_repeated`. Findings and changes:

- **Retries repeated the same note.** The model is nearly deterministic for an identical prompt, and a retry changed only the cache nonce, so it reproduced the rejected note. Retries now carry a plain explanation of why the last attempt failed (`feedback.py`).
- **Unit complaints were the planned noise.** Notes stating a lab in its alternate unit (Velorin index in mmol/L with range 3.89-7.21) are deliberate noise and realistic, but the glossary listed one unit per test, so the reviewer called them inconsistent. The glossary (reviewer and rating app) now gives each test's second unit and converted range, and says either unit is normal and that abnormal or unremarked values are not by themselves a tell. A value in the unusual unit must also keep its unit in the note (shorthand had dropped it, leaving "BRE 0.549" meaningless).
- **Stale values** in copy_forward (0.55-0.8 or 1.25-1.7 times the true value) look like unremarked critical values to the reviewer. They are part of the dataset by design and realistic for copied-forward text, so they are left in; the reviewer is told that out-of-range values are normal in real charts.
- **The recorded demo missed a setting.** `--max-notes 15` took the first 15 notes of the shuffled sheet, which by chance held one ai_scribe note. A browser run limited by `--max-notes` now rates a sample spread evenly over the four settings (interleaved, template controls left out), chosen by the command from the key; the reviewer still sees only notes.
- **Flags at a boundary.** A value of 0.5996 printed as 0.6 but was flagged low. Flags are now judged on the printed value.

### What AI scribe tools actually produce (research, added after round 3)

A reviewer of the round-3 recording expected the ai_scribe setting to look like a whole conversation. Published descriptions and studies of ambient scribes (vendor documentation and evaluations; sources in the proposal notes) agree that the tool records the visit conversation, transcribes it, and then drafts a structured clinical note, usually SOAP or a variant, for the clinician to review and sign. The transcript is a separate artifact, not the note. Features that matter here:

- **Structured and sectioned**, with History of Present Illness, Assessment and Plan, sometimes problem-based, and optional structured data.
- **Third-person paraphrase** ("The patient reports improved breathing"), plain full words, not clinician shorthand, and no quoting of the patient.
- **Only what was said aloud**: an unread-out value (a blood pressure never spoken) is simply absent. So labs appear only as results reviewed or discussed, which is what the setting now does.
- **Longer and more thorough than clinician notes, less concise**; stock closing sentences are common; errors are mostly omissions, with some additions.

The earlier setting asked for hedged flowing prose with patient quotes and "labs in passing", which matched none of this. It now uses four headed layouts as traits, no quotes, a "reviewed with the patient" treatment of results, and optional stock sentences ("The patient verbalized understanding."). The setting's opener limit is looser (45%) because scribe notes legitimately start with the same heading. A *transcript* of the conversation would be a different input type for a different eval (reading a dialogue); it is out of scope here and noted as possible later work. The copy_forward openers are now literal stock lines drawn by trait, because round 3 showed the model reused the sample opening line the prompt gave it in half of its notes.

Recording labels: the demo recording shows each note's kind in a corner of the page. The driver draws it from the key; no tool returns it, so the reviewer model stays blind and the human rating app is unchanged.

### Raters are told the kind of note (added after round 3)

The reviewer was kept blind to the setting, which made it judge an AI-scribe draft by the standard of a human's note and reject it as "tidy" or "mechanical", which is exactly what such tools produce (see the research above). The same holds for an EHR template. So every rater now sees each note's kind and what is normal for it, in the rating app and in the reviewer's prompt; the question becomes "is this a convincing example of that kind?", which is the question the gate per setting is really asking. What stays hidden is the answer: plan, extractor reading, record and internal setting name. The template-fixture controls are described as a plain clinician-written note, because telling the reviewer they are controls would defeat the discrimination check. The per-note kinds are written into `sheet.json` for new pilots and added from the key for older rounds when the reviewer command runs (a dry run writes nothing). The recording-only label drawn by the driver was dropped, as the page itself now shows the kind. Reviewer prompt version 4.

Trade-off: a reviewer told "tidy is expected" can be too generous to a genuinely bad scribe note. The reviewer still judges whether it reads like real scribe output, and the controls check still has to pass.

### What round 4 showed (added after the fourth review)

With the ai_scribe redesign and kind-aware raters, the direct review rated 79 of 80 notes plausible and the browser run 16 of 16. Three follow-ups:

- **A lenient reviewer is not a result.** Round 4 had no template controls, so the check that the reviewer rates bad notes lower never ran. Controls now go into every pilot round, a fresh set each round, and the reviewer should also be run on round 0, whose notes were known to be weak, before its verdict on later rounds is trusted.
- **ai_scribe was still rejecting natural wording** (26% exclusions, over the 15% gate limit). The replay of rejected attempts showed "denies any shaking or tremor" and "joint stiffness and morning stiffness" flagged as padding, which scribe prose does naturally. For ai_scribe the repetition limit is a third wording in a sentence or a fourth anywhere; terse and templated settings keep the stricter limit. The same replay passes 31 of 34 first attempts (from 9 of 39).
- **Smaller fixes:** the exemplar-copy check now needs ten plain words in a row and exempts stock sentences as well as stock lines; the copy_forward opener limit is 45%, since 40% of 20 notes from four equal stock openers is within chance.

### Round 5 and calibrating the reviewer (added after the fifth review)

Round 5 used the writer with all fixes, and the reviewer prompt version 4 (told each note's kind and the fictional panel). Direct review: shorthand 19/20, ehr_template 19/20, ai_scribe 20/20, copy_forward 19/20 plausible (96% overall); exclusions 0 to 9% (limit 15%); variety passes for all four settings; extractor agreement 1.00 on every flag. The 8 fresh template controls were rated plausible 4 of 8 (50%), a 46-point gap below the LLM notes (limit 20). The gate passes with `llm` accepted, and says so ("rated by: llm (not a clinician)").

Calibration: to show that a lenient reviewer is not what produced those numbers, the same reviewer was run on round 0, whose notes carried the known tells (four-digit lab values, "c/o denies", synonym padding, "fictional study condition"). It rated 44 of 80 of them plausible (shorthand 12/20, ehr_template 11/20, ai_scribe 16/20, copy_forward 5/20) and 2 of 8 round-0 controls, so it separates the old notes from the revised ones (55% against 96%). The reviewer file of an earlier prompt version left in a round's folder is not comparable and should be removed before a gate over several rounds (it was non-discriminating on one control); the final gate is run on the latest round.

The cost estimate for the full run at default sizes is about $2.68 (6,020 notes; about 11,550 first-attempt calls and 2,900 expected retries, 489 already cached), calibrated from the pilot cache, well under the $15 cap.

### The full run (added after task 8.2)

`data-gen generate --note-source llm --yes` wrote `data_llm/`: 5,639 records (train 3,798, test 1,438 holding 931 unique patients, adversarial 403) from 6,020 planned notes. 14,393 paid calls (the estimate said about 14,440) and about $2.72 (estimate $2.68), with 701 calls served from the pilot cache. Exclusions: 292 notes (4.9%), per setting ai_scribe 5.9%, copy_forward 6.7%, ehr_template 2.6%, shorthand 4.2%, all under the 15% limit; 31 of 200 matched-pair groups were dropped because a member was excluded (their other members went with them). Most rejected attempts were retried successfully: of 8,818 note attempts that failed validation, the top codes were symptom_repeated (2,924), polarity (595), exemplar_copied (181), phrase_missing (116) and meta_commentary (68).

Verification: `data-gen validate` passes; regenerating from the cache with a dummy key made 0 paid calls (15,094 cache hits) and reproduced the three splits and the README byte for byte (the manifest differs only in its call, cache-hit and spend counters, so the committed manifest keeps the real run's provenance); every note passes the identifier, claims, meta-mention, "c/o denies" and setting-name scans (0 hits in 5,639 records); no API key pattern appears in the dataset, the caches or the repository; sizes are 14 MB (dataset) and 6.5 MB (cache). The manifest records the realism review as "an LLM review, not a clinician". Note lengths (median words): shorthand 17, copy_forward 42, ehr_template 67, ai_scribe 86. The prompt version in the manifest is "2" for the whole revision history of that version; `prompt_text_hashes` pins the exact prompt and exemplar text.

## Risks / Trade-offs

- [A too-small output limit silently truncates notes, and a validator bug makes good notes look bad (both happened in the first real pilot: Haiku 5.5 thinks by default and thinking counts against `max_tokens`, and a lab whose name and abbreviation contain digits was misread)] → Default `max_tokens` 2000; a `max_tokens` stop is its own failure (`truncated`) and is never validated as if complete; the parser skips a lab's own parenthesised restatement; a setting is stopped early when most of its first attempts fail, and a full run stops when most notes fail, so no money is spent on retries that cannot help; every run prints live progress and `-v` logs each call.
- [LLM rewrites a value, drops a symptom or invents clinical detail] → Two-part validation, denylist scan, bounded retries, human gate, exclusions counted.
- [Settings sound alike because one model wrote them] → Distinct profile prompts and plan rules, measurable form checks in the spec, and the blind rating with controls.
- [Single rater and a plausibility notion that is not clinical] → Documented as a non-goal; ratings committed so others can audit; the gate is a smoke test, not validation.
- [Extractor shares the writer model's blind spots] → Different prompt and a hand-checked 80-note sample with a 0.95 threshold that blocks the run.
- [Exclusions bias the dataset toward easy notes] → Report exclusion rates by setting and noise type; investigate before publishing numbers.
- [Matched pairs double count patients in pooled metrics] → `pair_group` is required to be usable for deduplication.
- [Prose still carries LLM tics a classifier can learn] → Held-out-setting experiments in later changes, which this data is designed to support.
- [Cache or datasets grow large or leak a key] → Size check and key-pattern scan in the integration tasks.
- [Provider model deprecation changes outputs on regeneration] → Model id and prompt version are in the cache key and manifest; the committed cache preserves the published data.

## Open Questions

- Maximum retry count and the pilot exclusion threshold. Defaults: 3 attempts and 15%, adjustable in config without touching the spec.
- The number of matched-pair patients (default 200) and the setting mix for train and test (default equal shares). Config values.
