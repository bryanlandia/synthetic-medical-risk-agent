---
license: other
license_name: "no-license-demonstration-only"
tags:
- "synthetic-data"
- "fictional-disease"
- "not-for-clinical-use"
- "tabular-classification"
model-index:
- name: "Note reader and risk classifier (FICTIONAL disease)"
  results:
  - task:
      type: tabular-classification
      name: "Risk of a fictional disease from synthetic labs and a note"
    dataset:
      name: "data_llm (synthetic; not a Hub dataset), config hash 8151340e6ce1549d"
      type: "synthetic-medical-risk-agent/data_llm"
      split: "dev"
    metrics:
    - type: "auc"
      value: 0.7976
      name: "AUC"
    - type: "brier"
      value: 0.1581
      name: "Brier score"
    - type: "log_loss"
      value: 0.4828
      name: "Log loss"
    - type: "ece"
      value: 0.032
      name: "Expected calibration error"
  - task:
      type: tabular-classification
      name: "Risk of a fictional disease from synthetic labs and a note"
    dataset:
      name: "data_llm (synthetic; not a Hub dataset), config hash 8151340e6ce1549d"
      type: "synthetic-medical-risk-agent/data_llm"
      split: "test"
    metrics:
    - type: "auc"
      value: 0.7955
      name: "AUC"
    - type: "brier"
      value: 0.1553
      name: "Brier score"
    - type: "log_loss"
      value: 0.4827
      name: "Log loss"
    - type: "ece"
      value: 0.0422
      name: "Expected calibration error"
---

# Model Card for the note reader and risk classifier

**ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.**

A small CPU model that estimates the probability that a record has a **fictional** disease (Velorin-Kessler syndrome) from a fictional lab panel and a clinical note.

## Model Details

### Model Description

- **Developed by:** Bryan Wilson (https://github.com/bryanlandia/synthetic-medical-risk-agent)
- **Model type:** a note reader (logistic regression on word features) feeding a logistic risk classifier, with report assembly by code
- **Language(s):** English (synthetic clinical notes)
- **License:** No license is granted; this is purely for demonstration
- **Finetuned from model:** none; both parts are trained from scratch
- **Model hash:** `414c2d467c87d44bbf3cd8d92454a4041a133f9bc2403b11a521e59ee8191443`
- **MLflow run:** `6d59a45523694146a360b5191c11343b` (local store, not committed)
- **Seed:** 0; dataset `data_llm` (config hash `8151340e6ce1549d`)

### Model Sources

- **Repository:** https://github.com/bryanlandia/synthetic-medical-risk-agent
- **Demo:** none yet

## Uses

### Direct Use

A portfolio demonstration of a small, CPU-served model next to a prompted frontier model, scored by the same code-graded evals. It returns a probability, an uncertain flag, symptom readings, data-quality warnings and evidence for one record.

### Downstream Use

The chat service in `agent/` calls it as its only scoring tool; the model decides nothing about the numbers it returns.

### Out-of-Scope Use

Any real patient, any real disease and any real decision. It is **not medical advice**. It was fitted to a synthetic rule and says nothing about real clinical data.

## Bias, Risks, and Limitations

- **Missing labs.** A missing lab sits at the typical value with its indicator on; the model cannot know where the real value was. Most borderline failures on dev are records with a missing lab.
- **Label noise.** Labels are drawn from a probability, so some patients are on the wrong side of 0.5 for any system; the oracle's AUC on dev is 0.817.
- **The synthetic rule is logistic.** The data-generating rule is logistic in the labs and the true symptom flags, so a logistic model is well specified for it. A good result here says the pipeline works on this synthetic task, not what a real disease would allow.
- **`note_flag_disagreement`.** In this data the label means the note disagrees with the hidden flag, which cannot be seen from the record. The model warns only when a note contradicts itself with high confidence, so its recall for the labelled cases is expected to be near zero.
- **The lexicon and cue words come from the train notes and general English.** A symptom described with a word outside the lexicon is read as not mentioned.
- **Dev is slightly optimistic.** The regularisation and the conflict rule were chosen on dev.

### Recommendations

Use it only to study how the pipeline and its evals behave. Do not use it for any real person.

## How to Get Started with the Model

From the repository (the `risk_model` package needs only numpy):

```python
import risk_model
from risk_model import intake

model = risk_model.load()  # reads training/model, or the directory in RISK_MODEL_DIR
report = model.report(intake.view_from_text("Velorin index 128 mg/dL; Serum K-17 3.6 mmol/L. Tremor present."))
print(report["probability"], report["uncertain"])
```

## Training Details

### Training Data

Trained on 3298 train-split records (the LLM-written notes in `data_gen/data_llm/`), **excluding the 500 dev records**. Dev was used to choose the regularisation and the conflict rule. `test` and `adversarial` are scored once each with `--final`. Train ids hash `b5c94729c7595e9d`, dev ids hash `7be4d134599b69aa`.

### Training Procedure

- A **note reader** finds mentions of five symptoms in the note, classifies each as present, possible, absent or not about the patient, and reads the lab values the note states. Plain logistic regression on word features; no language model and no network.
- A **risk classifier**: a logistic regression on eight lab z-scores, eight missing-value indicators and the reader's symptom readings, with Platt scaling fitted on out-of-fold predictions (kept).
- **Report assembly** by code: `uncertain` is true exactly when the probability is in [0.4, 0.6]; data-quality warnings come from the panel and the note's stated values; evidence comes from fixed templates. Nothing is written by a model.

#### Training Hyperparameters

- Regularisation C = 0.1, chosen on dev; out-of-fold log loss 0.4820 before Platt scaling and 0.4818 after.
- Seed 0. Two runs with the same seed give byte-identical model files.

#### Speeds, Sizes, Times

Model files 197 kB. One report at a time on 1 thread: median 0.25 ms, 95th percentile 0.80 ms (500 dev records). Training time is not measured.

## Evaluation

### Testing Data, Factors & Metrics

Dev (500 patients, used to choose settings) and the protected `test` and `adversarial` splits (one look each). Metrics are the harness's: AUC, Brier score, log loss and ECE for the probability, plus symptom-reading accuracy, data-quality recall, borderline behavior and safety checks, each with a patient-clustered 95% interval and a target (v1).

### Results

#### Dev

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

#### Final results (one look each)

##### test

| Category | Metric | Value [95% interval] | Target v1 |
|---|---|---|---|
| happy_path | auc | 0.7955 [0.7620, 0.8274] | >= 0.7994: not reached, not distinguishable |
| happy_path | brier | 0.1553 [0.1429, 0.1688] | <= 0.1587: reached, not distinguishable |
| happy_path | log_loss | 0.4827 [0.4486, 0.5202] | <= 0.4822: not reached, not distinguishable |
| happy_path | ece | 0.0422 [0.0292, 0.0690] | <= 0.0643: reached, not distinguishable |
| symptom_reading | accuracy | 0.9940 [0.9916, 0.9963] | >= 0.6642: reached, clearly met |
| fabrication | rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | >= 1.0000: reached, clearly met |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| data_quality | recall:missing_value | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:unit_mismatch | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:contradiction | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | exact_match | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| borderline | uncertain_rate | 0.5838 [0.4835, 0.6813] | >= 0.5000: reached, not distinguishable |
| borderline | false_uncertain_rate | 0.0047 [0.0000, 0.0123] | <= 0.1000: reached, clearly met |
| consistency | mean_sd | 0.0109 [0.0087, 0.0131] |  |
| consistency | pass_rate | 0.9822 [0.9645, 1.0000] |  |

##### adversarial

| Category | Metric | Value [95% interval] | Target v1 |
|---|---|---|---|
| fabrication | rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | >= 1.0000: reached, clearly met |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| data_quality | recall:missing_value | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:unit_mismatch | 0.9818 [0.9455, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:impossible_value | 1.0000 [1.0000, 1.0000] |  |
| data_quality | recall:contradiction | 1.0000 [1.0000, 1.0000] | >= 0.5000: reached, clearly met |
| data_quality | recall:note_flag_disagreement | 0.0175 [0.0000, 0.0526] |  |
| data_quality | exact_match | 0.8000 [0.7509, 0.8456] | >= 0.5000: reached, clearly met |
| borderline | uncertain_rate | 0.6091 [0.5180, 0.7000] | >= 0.5000: reached, clearly met |
| borderline | false_uncertain_rate | 0.0140 [0.0000, 0.0350] | <= 0.1000: reached, clearly met |
| adversarial | resistance_rate | 1.0000 [1.0000, 1.0000] |  |

##### trials

| Category | Metric | Value [95% interval] | Target v1 |
|---|---|---|---|
| fabrication | rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| safety | pass_rate | 1.0000 [1.0000, 1.0000] | >= 1.0000: reached, clearly met |
| parse | failure_rate | 0.0000 [0.0000, 0.0000] | <= 0.0000: reached, clearly met |
| consistency | mean_sd | 0.0109 [0.0087, 0.0131] |  |
| consistency | pass_rate | 0.9822 [0.9645, 1.0000] |  |

## Model Examination

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

## Environmental Impact

Not measured. Both parts are small, train and run on a CPU, and no energy or time figure is given.

## Technical Specifications

### Model Architecture and Objective

Two logistic regressions (the reader and the classifier) stored as JSON (`reader.json`, `classifier.json`); the objective is log loss. The model hash is the SHA-256 over those two files' names and bytes.

### Compute Infrastructure

Training: scikit-learn on a CPU, tracked with MLflow. Inference: the `risk_model` package, numpy only, on a CPU.

## Citation

None.

## Glossary

All labs and symptoms are fictional.

| Lab | Abbreviation | Unit | Typical value | Reference range |
|---|---|---|---|---|
| Velorin index | VLI | mg/dL | 100 | 70 to 130 |
| Serum K-17 | K17 | mmol/L | 4.2 | 3.4 to 5 |
| Tarnic acid | TAC | umol/L | 300 | 200 to 400 |
| Brell enzyme | BRE | U/L | 35 | 15 to 55 |
| Halvin titer | HAT | g/dL | 4 | 3 to 5 |
| Osmet level | OSM | mOsm/kg | 290 | 270 to 310 |
| Plexa count | PLX | x10^9/L | 250 | 150 to 400 |
| Dorrin ratio | DOR | ratio | 1 | 0.6 to 1.4 |

Symptoms the reader looks for: tremor, fatigue, photophobia, joint stiffness, dizziness. Each is read as present, possible, absent or not about the patient. `uncertain` means the probability is in [0.4, 0.6].

## More Information

Reproduce, from `training/`: `uv run training train` (fits both parts, scores dev, writes `model/` and logs an MLflow run), then `uv run evals run --system classifier --split dev`. A test checks that the committed card is exactly what these files say.

## Model Card Authors

Bryan Wilson

## Model Card Contact

Open an issue at https://github.com/bryanlandia/synthetic-medical-risk-agent.
