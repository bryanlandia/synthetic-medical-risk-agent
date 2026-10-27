# Model card: note reader and risk classifier

**ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.**

- Model hash: `414c2d467c87d44bbf3cd8d92454a4041a133f9bc2403b11a521e59ee8191443`
- MLflow run: `6d59a45523694146a360b5191c11343b` (local store, not committed)
- Seed: 0; dataset `data_llm` (config hash `8151340e6ce1549d`)

## Intended use

A portfolio demonstration of a small, CPU-served model next to a prompted frontier model, scored by the same code-graded evals. It estimates the probability that a record has a **fictional** disease (Velorin-Kessler syndrome) from a fictional lab panel and a clinical note. It is **not medical advice** and must not be used for any real patient, disease or decision.

## What it is

- A **note reader** finds mentions of five symptoms in the note, classifies each as present, possible, absent or not about the patient, and reads the lab values the note states. Plain logistic regression on word features; no language model and no network.
- A **risk classifier**: a logistic regression on eight lab z-scores, eight missing-value indicators and the reader's symptom readings, with Platt scaling fitted on out-of-fold predictions (kept). Chosen regularisation C = 0.1.
- **Report assembly** by code: `uncertain` is true exactly when the probability is in [0.4, 0.6]; data-quality warnings come from the panel and the note's stated values; evidence comes from fixed templates. Nothing is written by a model.

## Data and splits

Trained on 3298 train-split records (the LLM-written notes in `data_gen/data_llm/`), **excluding the 500 dev records**. Dev was used to choose the regularisation and the conflict rule. `test` and `adversarial` are scored once each with `--final`. Train ids hash `b5c94729c7595e9d`, dev ids hash `7be4d134599b69aa`.

## Dev results

Source: `evals run --system classifier --split dev` (harness numbers, 500 patients).

| Category | Metric | Value [95% interval] | Target v1 |
|---|---|---|---|
| happy_path | auc | 0.7976 [0.7541, 0.8403] | >= 0.7994: not reached, not distinguishable |
| happy_path | brier | 0.1581 [0.1387, 0.1775] | <= 0.1587: reached, not distinguishable |
| happy_path | log_loss | 0.4828 [0.4334, 0.5360] | <= 0.4822: not reached, not distinguishable |
| happy_path | ece | 0.0320 [0.0280, 0.0794] | <= 0.0643: reached, not distinguishable |
| symptom_reading | accuracy | 0.9952 [0.9924, 0.9980] | >= 0.6642: reached, clearly met |
| data_quality | exact_match | 0.9957 [0.9827, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:missing_value | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9828 [0.9483, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:contradiction | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| borderline | uncertain_rate | 0.5132 [0.4079, 0.6316] | >= 0.5000: reached, not distinguishable |
| borderline | false_uncertain_rate | 0.0135 [0.0000, 0.0270] | <= 0.1000: reached, clearly met |
| fabrication | rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | >= 1.0000: reached, clearly met |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |

- Probabilities on dev: 5th percentile 0.034, median 0.228, 95th percentile 0.804; 13.0% of reports are in the uncertain band.
- A gradient-boosted model on the same features scored AUC 0.7754, Brier 0.1672, log loss 0.5051 on dev. It is a diagnostic and is never served.

## Note reader

Symptom-reading accuracy on dev: 0.9952 [0.9924, 0.9980] (floor 0.95). Conflict rule `confident`, chosen on dev ({'confident': 0.9952, 'last': 0.9912}).

Leave-one-setting-out (trained on three documentation settings, scored on the fourth):

| Held-out setting | With shared cue words | Without | In-distribution |
|---|---|---|---|
| shorthand | 0.9847 [0.9812, 0.9881] | 0.9651 [0.9600, 0.9701] | 0.9985 |
| ehr_template | 0.9599 [0.9532, 0.9662] | 0.7417 [0.7259, 0.7574] (below 0.90) | 0.9959 |
| ai_scribe | 0.9771 [0.9727, 0.9811] | 0.9433 [0.9366, 0.9496] | 0.9964 |
| copy_forward | 0.9786 [0.9741, 0.9829] | 0.9793 [0.9752, 0.9833] | 0.9895 |

**Finding.** Without the shared cue words, the reader fails on a setting it has not seen: the EHR template is the only setting that writes "Negative for ..." and "Positive for ...", so with it held out the word "negative" was unknown and absent symptoms were read as present. Adding three small groups of general-English cue words (negation, hedge, affirmation) as shared features removes the gap. The cue lists are not taken from this data.

Injection: with each of the catalog's addenda appended to every dev note, the readings were identical for 4000 of 4000 pairs (100.0%). The real injection records are in the protected adversarial split and are scored only by the final run.

## Size and speed

Model files 197 kB. One report at a time on 1 thread: median 0.25 ms, 95th percentile 0.80 ms (500 dev records).

## Known weaknesses

- **Missing labs.** A missing lab sits at the typical value with its indicator on; the model cannot know where the real value was. Most borderline failures on dev are records with a missing lab.
- **Label noise.** Labels are drawn from a probability, so some patients are on the wrong side of 0.5 for any system; the oracle's AUC on dev is 0.817.
- **The synthetic rule is logistic.** The data-generating rule is logistic in the labs and the true symptom flags, so a logistic model is well specified for it. A good result here says the pipeline works on this synthetic task, not what a real disease would allow.
- **`note_flag_disagreement`.** In this data the label means the note disagrees with the hidden flag, which cannot be seen from the record. The model warns only when a note contradicts itself with high confidence, so its recall for the labelled cases is expected to be near zero.
- **The lexicon and cue words come from the train notes and general English.** A symptom described with a word outside the lexicon is read as not mentioned.
- **Dev is slightly optimistic.** The regularisation and the conflict rule were chosen on dev.

## Reproduce

From `training/`: `uv run training train` (fits both parts, scores dev, writes `model/` and logs an MLflow run), then `uv run evals run --system classifier --split dev`. Two runs with the same seed give byte-identical model files (a test checks it).
