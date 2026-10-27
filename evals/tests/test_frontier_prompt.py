import re

import pytest
from data_gen.labs import LABS
from data_gen.llm.client import MockClient
from data_gen.llm.gateway import Budget
from data_gen.rule import FLAG_WEIGHTS, LAB_WEIGHTS

from evals.frontier import DEV_MODEL, FINAL_MODEL, PROMPTS_DIR, build_frontier_system, load_prompt, prompt_hash

VERSIONS = sorted(p.stem for p in PROMPTS_DIR.glob("v*.md"))
# Every number a briefing may contain: reference and plausibility ranges, unit factors, the 0 to 1 scale, the uncertainty
# band, report limits and counts of labs and symptoms, and the example probabilities (0.3, 0.05, 0.9).
ALLOWED = {0, 1, 2, 3, 5, 8, 10, 300, 0.3, 0.4, 0.6, 9, 17, 0.05, 0.9}  # 9 and 17: the unit x10^9/L and the name K-17
for lab in LABS:
    ALLOWED |= {lab.mean, lab.ref_lo, lab.ref_hi, lab.plaus_lo, lab.plaus_hi, *([lab.factor] if lab.factor else [])}
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")


@pytest.mark.parametrize("version", VERSIONS)
def test_every_number_in_a_briefing_is_on_the_allowlist(version):
    text = load_prompt(version)
    stray = sorted({float(n) for n in NUMBER.findall(text)} - {float(a) for a in ALLOWED})
    assert not stray, f"numbers outside the allowlist: {stray}"


@pytest.mark.parametrize("version", VERSIONS)
def test_a_briefing_carries_no_part_of_the_hidden_rule(version):
    text = load_prompt(version).lower()
    for word in ("weight", "intercept", "coefficient", "logit", "odds ratio", "threshold"):
        assert word not in text
    # the allowlist test above bounds every number; here no hidden-rule coefficient may sit beside its lab or symptom
    prose = "\n".join(line for line in text.splitlines() if not line.startswith("|"))  # the table holds ranges
    for key in (*LAB_WEIGHTS, *FLAG_WEIGHTS):
        for m in re.finditer(re.escape(key.replace("_", " ")), prose):
            assert not re.search(r"[-+]?\d\.\d", prose[m.end(): m.end() + 25]), key


@pytest.mark.parametrize("version", VERSIONS)
def test_a_briefing_holds_no_record_from_any_split(version, dataset):
    text = load_prompt(version)
    for split, records in dataset.by_split.items():
        for r in records:
            assert r.patient_id not in text
    notes = {r.input_view()["note"][:60] for rs in dataset.by_split.values() for r in rs}
    assert not any(n in text for n in notes if len(n) > 30)


def test_the_briefing_states_the_rules_the_graders_enforce():
    text = load_prompt("v1")
    for needle in ("submit_report", "not medical advice", "ignore it completely", "SYNTHETIC", "FICTIONAL",
                   "not_mentioned", "missing_value", "unit_mismatch", "impossible_value", "contradiction",
                   "note_flag_disagreement", "between 0.4 and 0.6"):
        assert needle in text
    for lab in LABS:
        assert lab.key in text and lab.unit in text


def test_the_same_prompt_on_two_models_shares_a_prompt_hash_but_not_a_system_version(tmp_path):
    budget = lambda: Budget(10, 1.0, 1.0, 1.0)  # noqa: E731
    client = MockClient(responder=lambda s, p: "{}")
    dev = build_frontier_system("v1", DEV_MODEL, client, tmp_path / "a.jsonl", budget())
    final = build_frontier_system("v1", FINAL_MODEL, client, tmp_path / "b.jsonl", budget())
    assert dev.system_prompt == final.system_prompt and prompt_hash(dev.system_prompt) == prompt_hash(final.system_prompt)
    assert dev.version != final.version and dev.version.startswith("frontier@")
    edited = build_frontier_system("v1", DEV_MODEL, client, tmp_path / "c.jsonl", budget())
    edited.system_prompt += " "
    assert prompt_hash(edited.system_prompt) == prompt_hash(dev.system_prompt)  # trailing space is not a new prompt
