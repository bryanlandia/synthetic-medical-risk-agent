import json
import re
import shutil
from pathlib import Path

import yaml
from risk_model.labs import LABS

from training import model_card, pipeline

MODEL = Path(__file__).resolve().parents[1] / "model"
RESULTS = Path(__file__).resolve().parents[2] / "evals" / "results" / "classifier"
TEMPLATE_HEADINGS = [
    "Model Details", "Uses", "Bias, Risks, and Limitations", "How to Get Started with the Model", "Training Details", "Evaluation",
    "Model Examination", "Environmental Impact", "Technical Specifications", "Citation", "Glossary", "More Information",
    "Model Card Authors", "Model Card Contact"]


def _card() -> str:
    return (MODEL / model_card.CARD_NAME).read_text()


def _metadata(card: str) -> dict:
    assert card.startswith("---\n")
    return yaml.safe_load(card.split("---\n", 2)[1])


def test_the_committed_card_names_the_hash_of_the_committed_model_files():
    assert pipeline.model_hash(MODEL) in _card()
    assert json.loads((MODEL / "manifest.json").read_text())["model_hash"] == pipeline.model_hash(MODEL)


def test_the_committed_card_is_exactly_what_the_files_say():
    assert _card() == model_card.render(MODEL)


def test_changing_a_model_file_makes_the_card_stale(tmp_path):
    shutil.copytree(MODEL, tmp_path / "m")
    m = tmp_path / "m"
    (m / "classifier.json").write_text(json.dumps({**json.loads((m / "classifier.json").read_text()), "intercept": 0.123}))
    assert pipeline.model_hash(m) not in (m / model_card.CARD_NAME).read_text()


def test_the_card_has_the_template_sections_in_the_templates_order():
    headings = re.findall(r"^## (.+)$", _card(), flags=re.M)
    assert headings == TEMPLATE_HEADINGS
    assert re.findall(r"^### (Direct Use|Downstream Use|Out-of-Scope Use)$", _card(), flags=re.M) == [
        "Direct Use", "Downstream Use", "Out-of-Scope Use"]


def test_the_card_states_the_notice_the_license_the_out_of_scope_use_and_the_findings():
    card = _card()
    out_of_scope = card.split("### Out-of-Scope Use")[1].split("##")[0]
    assert "Any real patient" in out_of_scope and "not medical advice" in out_of_scope
    for needle in ("ALL DATA IS SYNTHETIC", "Finetuned from model:** none", "No license is granted; this is purely for demonstration",
                   "Developed by:** Bryan Wilson", "Leave-one-setting-out", "Negative for", "excluding the 500 dev records",
                   "never served", "Not measured"):
        assert needle in card, needle


def test_the_metadata_equals_the_result_files():
    meta = _metadata(_card())
    assert meta["license"] == "other" and {"synthetic-data", "fictional-disease", "not-for-clinical-use"} <= set(meta["tags"])
    results = {r["dataset"]["split"]: r for r in meta["model-index"][0]["results"]}
    assert set(results) == {"dev", "test"}
    for split, entry in results.items():
        rows = {(r["category"], r["metric"]): r["value"] for r in json.loads((RESULTS / split / "summary.json").read_text())["rows"]}
        got = {m["type"]: m["value"] for m in entry["metrics"]}
        assert set(got) == {"auc", "brier", "log_loss", "ece"}
        for metric, value in got.items():
            assert value == round(rows[("happy_path", metric)], 4), (split, metric)


def test_the_glossary_lists_every_lab_the_code_uses():
    glossary = _card().split("## Glossary")[1].split("## More Information")[0]
    for lab in LABS:
        assert f"| {lab.name} | {lab.abbr} | {lab.unit} |" in glossary


def test_the_example_in_the_card_runs_against_the_committed_model():
    block = re.search(r"## How to Get Started with the Model.*?```python\n(.*?)```", _card(), flags=re.S).group(1)
    scope: dict = {}
    exec(compile(block, "model-card-example", "exec"), scope)  # noqa: S102 - the card is our own generated file
    assert 0.0 <= scope["report"]["probability"] <= 1.0
