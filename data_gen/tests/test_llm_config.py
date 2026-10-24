import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_gen.config import AVAILABLE_STYLES, LLM_SETTINGS, GenConfig, LLMConfig

DATA = Path(__file__).resolve().parents[1] / "data"


def test_defaults_are_sane():
    c = LLMConfig()
    assert c.model_id == "claude-haiku-5-5"
    assert c.max_attempts == 3 and c.pilot_per_setting == 20 and c.matched_pairs == 200
    assert c.exclusion_threshold == 0.15
    assert c.pilot_max_calls < c.max_calls and c.pilot_max_spend_usd < c.max_spend_usd


@pytest.mark.parametrize(
    "bad",
    [
        {"max_attempts": 0},
        {"max_attempts": 11},
        {"max_calls": 0},
        {"max_spend_usd": 0},
        {"max_spend_usd": -1},
        {"pilot_max_calls": 0},
        {"pilot_per_setting": 0},
        {"matched_pairs": -1},
        {"exclusion_threshold": 1.5},
        {"exclusion_threshold": -0.1},
        {"max_tokens": 10},
        {"prompt_version": ""},
        {"price_input_per_mtok": -1},
        {"api_key": "x"},  # there is deliberately nowhere to put a key
        {"unknown_field": 1},
    ],
)
def test_bad_llm_config_values_are_rejected(bad):
    with pytest.raises(ValidationError):
        LLMConfig(**bad)


def test_llm_source_defaults_to_equal_setting_shares():
    c = GenConfig(note_source="llm")
    assert set(c.style_rates) == set(LLM_SETTINGS)
    assert all(abs(v - 0.25) < 1e-12 for v in c.style_rates.values())


def test_custom_llm_rates_must_sum_to_one_and_use_settings():
    ok = GenConfig(note_source="llm", style_rates={"shorthand": 0.4, "ehr_template": 0.6})
    assert ok.style_rates["ehr_template"] == 0.6
    with pytest.raises(ValueError, match="sum to 1"):
        GenConfig(note_source="llm", style_rates={"shorthand": 0.5, "ehr_template": 0.4})


def test_unknown_style_is_rejected_for_both_sources():
    for source in ("template", "llm"):
        with pytest.raises(ValueError, match="unknown styles"):
            GenConfig(note_source=source, style_rates={"cuneiform": 1.0})


def test_zero_rate_unsupported_style_is_allowed():
    c = GenConfig(style_rates={"terse": 0.5, "templated": 0.5, "ai_scribe": 0.0})
    assert c.note_source == "template"


def test_style_sets_do_not_overlap():
    assert not set(AVAILABLE_STYLES) & set(LLM_SETTINGS)


def test_canonical_dump_omits_new_fields_at_their_defaults():
    dump = GenConfig().canonical_dump()
    assert "note_source" not in dump and "llm" not in dump
    changed = GenConfig(note_source="llm").canonical_dump()
    assert changed["note_source"] == "llm" and "llm" not in changed  # llm block still default
    assert "llm" in GenConfig(llm=LLMConfig(max_attempts=5)).canonical_dump()


def test_template_dataset_config_hash_is_unchanged():
    manifest = json.loads((DATA / "manifest.json").read_text())
    cfg = GenConfig(**manifest["config"])
    assert cfg.config_hash() == manifest["config_hash"]
    assert cfg.canonical_dump() == manifest["config"]


def test_changing_llm_settings_changes_the_hash():
    assert GenConfig().config_hash() != GenConfig(llm=LLMConfig(prompt_version="2")).config_hash()
