"""The model card in the Hugging Face template, written from the manifest and the result files so that it cannot drift from the model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_gen import SYNTHETIC_NOTICE
from risk_model.labs import LABS, SYMPTOM_KEYS

from . import pipeline
from .eval_cli import RESULTS_DIR

CARD_NAME = "MODEL_CARD.md"
REPOSITORY = "https://github.com/bryanlandia/synthetic-medical-risk-agent"
AUTHOR = "Bryan Wilson"
LICENSE_LINE = "No license is granted; this is purely for demonstration"
RULE = "The data-generating rule is logistic in the labs and the true symptom flags, so a logistic model is well specified for it."
INDEX_METRICS = (("auc", "AUC"), ("brier", "Brier score"), ("log_loss", "Log loss"), ("ece", "Expected calibration error"))
TAGS = ("synthetic-data", "fictional-disease", "not-for-clinical-use", "tabular-classification")
EXAMPLE = '''```python
import risk_model
from risk_model import intake

model = risk_model.load()  # reads training/model, or the directory in RISK_MODEL_DIR
report = model.report(intake.view_from_text("Velorin index 128 mg/dL; Serum K-17 3.6 mmol/L. Tremor present."))
print(report["probability"], report["uncertain"])
```'''


def _read(path: Path) -> Any:
    return json.loads(path.read_text()) if path.exists() else None


def _cell(r: dict[str, Any]) -> str:
    return f"{r['value']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}]"


def _summary_rows(summary: dict[str, Any] | None, wanted: list[tuple[str, str]]) -> list[str]:
    if not summary:
        return []
    by = {(r["category"], r["metric"]): r for r in summary["rows"]}
    out = []
    for key in wanted:
        r = by.get(key)
        if r:
            tail = f"{'>=' if r['direction'] == 'higher' else '<='} {r['target']:.4f}: {'reached' if r['reached'] else 'not reached'}, {r['label']}" if "target" in r else ""
            out.append(f"| {key[0]} | {key[1]} | {_cell(r)} | {tail} |")
    return out


def _scalar(v: Any) -> str:
    return json.dumps(v)  # a JSON scalar is a YAML scalar, so no YAML library is needed to write the block


def _metadata(manifest: dict[str, Any], dev: dict[str, Any] | None, test: dict[str, Any] | None) -> list[str]:
    L = ["---", "license: other", f"license_name: {_scalar('no-license-demonstration-only')}", "tags:"]
    L += [f"- {_scalar(t)}" for t in TAGS]
    groups = [(split, s) for split, s in (("dev", dev), ("test", test)) if s]
    L += ["model-index:", f"- name: {_scalar('Note reader and risk classifier (FICTIONAL disease)')}", "  results:"]
    for split, summary in groups:
        by = {(r["category"], r["metric"]): r for r in summary["rows"]}
        L += ["  - task:", "      type: tabular-classification", f"      name: {_scalar('Risk of a fictional disease from synthetic labs and a note')}",
              "    dataset:", f"      name: {_scalar('data_llm (synthetic; not a Hub dataset), config hash ' + manifest['dataset_config_hash'])}",
              f"      type: {_scalar('synthetic-medical-risk-agent/data_llm')}", f"      split: {_scalar(split)}", "    metrics:"]
        for metric, name in INDEX_METRICS:
            L += [f"    - type: {_scalar(metric)}", f"      value: {round(by[('happy_path', metric)]['value'], 4)}", f"      name: {_scalar(name)}"]
    return L + ["---", ""]


def _glossary() -> list[str]:
    rows = ["| Lab | Abbreviation | Unit | Typical value | Reference range |", "|---|---|---|---|---|"]
    rows += [f"| {lab.name} | {lab.abbr} | {lab.unit} | {lab.mean:g} | {lab.ref_lo:g} to {lab.ref_hi:g} |" for lab in LABS]
    symptoms = ", ".join(k.replace("_", " ") for k in SYMPTOM_KEYS)
    return ["All labs and symptoms are fictional.", "", *rows, "", f"Symptoms the reader looks for: {symptoms}. Each is read as present, possible, "
            "absent or not about the patient. `uncertain` means the probability is in [0.4, 0.6]."]


def render(model_dir: Path = pipeline.MODEL_DIR, results_dir: Path = RESULTS_DIR) -> str:
    manifest = _read(model_dir / "manifest.json")
    metrics = _read(model_dir / "metrics.json")
    reader = _read(model_dir / "reader_report.json")
    run = _read(model_dir / "run.json") or {}
    latency = _read(results_dir / "latency.json")
    dev = _read(results_dir / "dev" / "summary.json")
    wanted = [("happy_path", m) for m in ("auc", "brier", "log_loss", "ece")] + [
        ("symptom_reading", "accuracy"), ("data_quality", "exact_match"), ("data_quality", "recall:missing_value"),
        ("data_quality", "recall:unit_mismatch"), ("data_quality", "recall:contradiction"), ("borderline", "uncertain_rate"),
        ("borderline", "false_uncertain_rate"), ("fabrication", "rate"), ("safety", "pass_rate"), ("parse", "failure_rate")]
    table = ["| Category | Metric | Value [95% interval] | Target v1 |", "|---|---|---|---|"]
    final = [(s, _read(results_dir / s / "summary.json")) for s in ("test", "adversarial", "trials")]
    test = dict(final).get("test")
    L = _metadata(manifest, dev, test)
    L += ["# Model Card for the note reader and risk classifier", "", f"**{SYNTHETIC_NOTICE}**", "",
          "A small CPU model that estimates the probability that a record has a **fictional** disease (Velorin-Kessler syndrome) "
          "from a fictional lab panel and a clinical note.", "",
          "## Model Details", "", "### Model Description", "",
          f"- **Developed by:** {AUTHOR} ({REPOSITORY})",
          "- **Model type:** a note reader (logistic regression on word features) feeding a logistic risk classifier, with report assembly by code",
          "- **Language(s):** English (synthetic clinical notes)",
          f"- **License:** {LICENSE_LINE}",
          "- **Finetuned from model:** none; both parts are trained from scratch",
          f"- **Model hash:** `{manifest['model_hash']}`",
          f"- **MLflow run:** `{run.get('mlflow_run_id', 'not recorded')}` (local store, not committed)",
          f"- **Seed:** {manifest['seed']}; dataset `{manifest['dataset']}` (config hash `{manifest['dataset_config_hash']}`)", "",
          "### Model Sources", "", f"- **Repository:** {REPOSITORY}", "- **Demo:** none yet", "",
          "## Uses", "", "### Direct Use", "",
          "A portfolio demonstration of a small, CPU-served model next to a prompted frontier model, scored by the same code-graded "
          "evals. It returns a probability, an uncertain flag, symptom readings, data-quality warnings and evidence for one record.", "",
          "### Downstream Use", "", "The chat service in `agent/` calls it as its only scoring tool; the model decides nothing about the numbers it returns.", "",
          "### Out-of-Scope Use", "",
          "Any real patient, any real disease and any real decision. It is **not medical advice**. It was fitted to a synthetic rule "
          "and says nothing about real clinical data.", "",
          "## Bias, Risks, and Limitations", "",
          "- **Missing labs.** A missing lab sits at the typical value with its indicator on; the model cannot know where the "
          "real value was. Most borderline failures on dev are records with a missing lab.",
          "- **Label noise.** Labels are drawn from a probability, so some patients are on the wrong side of 0.5 for any "
          "system; the oracle's AUC on dev is 0.817.",
          f"- **The synthetic rule is logistic.** {RULE} A good result here says the pipeline works on this synthetic task, not "
          "what a real disease would allow.",
          "- **`note_flag_disagreement`.** In this data the label means the note disagrees with the hidden flag, which cannot be seen "
          "from the record. The model warns only when a note contradicts itself with high confidence, so its recall for the "
          "labelled cases is expected to be near zero.",
          "- **The lexicon and cue words come from the train notes and general English.** A symptom described with a word outside "
          "the lexicon is read as not mentioned.",
          "- **Dev is slightly optimistic.** The regularisation and the conflict rule were chosen on dev.", "",
          "### Recommendations", "", "Use it only to study how the pipeline and its evals behave. Do not use it for any real person.", "",
          "## How to Get Started with the Model", "", "From the repository (the `risk_model` package needs only numpy):", "", EXAMPLE, "",
          "## Training Details", "", "### Training Data", "",
          f"Trained on {manifest['n_train']} train-split records (the LLM-written notes in `data_gen/data_llm/`), **excluding "
          "the 500 dev records**. Dev was used to choose the regularisation and the conflict rule. `test` and `adversarial` "
          "are scored once each with `--final`. Train ids hash "
          f"`{manifest['train_ids_sha256'][:16]}`, dev ids hash `{manifest['dev_ids_sha256'][:16]}`.", "",
          "### Training Procedure", "",
          "- A **note reader** finds mentions of five symptoms in the note, classifies each as present, possible, absent or "
          "not about the patient, and reads the lab values the note states. Plain logistic regression on word features; no "
          "language model and no network.",
          "- A **risk classifier**: a logistic regression on eight lab z-scores, eight missing-value indicators and the "
          "reader's symptom readings, with Platt scaling fitted on out-of-fold predictions"
          + (" (kept)" if metrics["chosen"]["platt"] else " (dropped: no gain)") + ".",
          "- **Report assembly** by code: `uncertain` is true exactly when the probability is in [0.4, 0.6]; data-quality "
          "warnings come from the panel and the note's stated values; evidence comes from fixed templates. Nothing is "
          "written by a model.", "", "#### Training Hyperparameters", "",
          f"- Regularisation C = {metrics['chosen']['c']}, chosen on dev; out-of-fold log loss {metrics['chosen']['oof_log_loss']['before']:.4f} before Platt scaling and {metrics['chosen']['oof_log_loss']['after']:.4f} after.",
          f"- Seed {manifest['seed']}. Two runs with the same seed give byte-identical model files.", ""]
    if latency:
        L += ["#### Speeds, Sizes, Times", "", f"Model files {latency['model_bytes'] / 1000:.0f} kB. One report at a time on {latency['threads']} thread: "
              f"median {latency['median_ms']:.2f} ms, 95th percentile {latency['p95_ms']:.2f} ms ({latency['records']} dev records). "
              "Training time is not measured.", ""]
    L += ["## Evaluation", "", "### Testing Data, Factors & Metrics", "",
          "Dev (500 patients, used to choose settings) and the protected `test` and `adversarial` splits (one look each). Metrics are "
          "the harness's: AUC, Brier score, log loss and ECE for the probability, plus symptom-reading accuracy, data-quality "
          "recall, borderline behavior and safety checks, each with a patient-clustered 95% interval and a target (v1).", "",
          "### Results", "", "#### Dev", "", "Source: `evals run --system classifier --split dev` (harness numbers, 500 patients).", ""]
    rows = _summary_rows(dev, wanted)
    L += [*table, *rows, ""] if rows else ["Not yet run.", ""]
    if metrics:
        p = metrics["probability_percentiles"]
        gbm = metrics["gbm_diagnostic"]
        L += [f"- Probabilities on dev: 5th percentile {p['5']:.3f}, median {p['50']:.3f}, 95th percentile {p['95']:.3f}; "
              f"{metrics['uncertain_share']:.1%} of reports are in the uncertain band.",
              f"- A gradient-boosted model on the same features scored AUC {gbm['auc']['value']:.4f}, Brier "
              f"{gbm['brier']['value']:.4f}, log loss {gbm['log_loss']['value']:.4f} on dev. It is a diagnostic and is never served.", ""]
    if any(f for _, f in final):
        L += ["#### Final results (one look each)", ""]
        for stage, summary in final:
            if summary:
                srows = _summary_rows(summary, [(r["category"], r["metric"]) for r in summary["rows"]])
                L += [f"##### {stage}", "", *table, *srows, ""]
    L += ["## Model Examination", ""]
    if reader:
        rd = reader["dev"]["accuracy"]
        L += [f"Symptom-reading accuracy on dev: {_cell(rd)} (floor {reader['dev']['floor']}). "
              f"Conflict rule `{reader['reader']['conflict_rule']}`, chosen on dev "
              f"({reader['reader']['conflict_rule_dev_accuracy']}).", "",
              "Leave-one-setting-out (trained on three documentation settings, scored on the fourth):", "",
              "| Held-out setting | With shared cue words | Without | In-distribution |", "|---|---|---|---|"]
        without = {r["held_out"]: r for r in reader["held_out"]["without_cues"]}
        for r in reader["held_out"]["with_cues"]:
            w = without[r["held_out"]]
            L.append(f"| {r['held_out']} | {_cell(r)} | {_cell(w)}{' (below 0.90)' if w['below_floor'] else ''} | {r['in_distribution']:.4f} |")
        inj = reader["injection"]
        L += ["", "**Finding.** Without the shared cue words, the reader fails on a setting it has not seen: the EHR template is the "
              "only setting that writes \"Negative for ...\" and \"Positive for ...\", so with it held out the word \"negative\" was "
              "unknown and absent symptoms were read as present. Adding three small groups of general-English cue words "
              "(negation, hedge, affirmation) as shared features removes the gap. The cue lists are not taken from this data.",
              "", f"Injection: with each of the catalog's addenda appended to every dev note, the readings were identical for "
              f"{inj['identical']} of {inj['pairs']} pairs ({inj['agreement']:.1%}). The real injection records are in the protected "
              "adversarial split and are scored only by the final run.", ""]
    L += ["## Environmental Impact", "", "Not measured. Both parts are small, train and run on a CPU, and no energy or time figure is given.", "",
          "## Technical Specifications", "", "### Model Architecture and Objective", "",
          "Two logistic regressions (the reader and the classifier) stored as JSON (`reader.json`, `classifier.json`); the "
          "objective is log loss. The model hash is the SHA-256 over those two files' names and bytes.", "",
          "### Compute Infrastructure", "",
          "Training: scikit-learn on a CPU, tracked with MLflow. Inference: the `risk_model` package, numpy only, on a CPU.", "",
          "## Citation", "", "None.", "",
          "## Glossary", "", *_glossary(), "",
          "## More Information", "",
          "Reproduce, from `training/`: `uv run training train` (fits both parts, scores dev, writes `model/` and logs an MLflow "
          "run), then `uv run evals run --system classifier --split dev`. A test checks that the committed card is exactly what "
          "these files say.", "",
          "## Model Card Authors", "", AUTHOR, "",
          "## Model Card Contact", "", f"Open an issue at {REPOSITORY}.", ""]
    return "\n".join(L)


def write(model_dir: Path = pipeline.MODEL_DIR, results_dir: Path = RESULTS_DIR) -> Path:
    path = model_dir / CARD_NAME
    path.write_text(render(model_dir, results_dir))
    return path


WEB_COPY = Path(__file__).resolve().parents[3] / "web" / "content" / "model-card.md"


def copy_to_web(model_dir: Path = pipeline.MODEL_DIR, dest: Path = WEB_COPY) -> Path:
    """The web page shows this copy; a test fails if it differs from the card in ``model/``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((model_dir / CARD_NAME).read_text())
    return dest
