import itertools

from data_gen.config import LLM_SETTINGS
from data_gen.labs import SYMPTOMS
from data_gen.settings import PROFILES


def test_every_symptom_has_enough_distinct_phrases():
    for s in SYMPTOMS:
        assert len(s.phrases) >= 3, s.key
        assert len(set(p.lower() for p in s.phrases)) == len(s.phrases), s.key
        assert s.name in s.phrases, f"{s.key}: the canonical name must be an allowed phrase"


def test_phrases_map_to_exactly_one_symptom():
    # No phrase equals, or is contained in, a phrase of a different symptom.
    for a, b in itertools.permutations(SYMPTOMS, 2):
        for pa in a.phrases:
            for pb in b.phrases:
                assert pa.lower() not in pb.lower(), (a.key, pa, b.key, pb)


def test_every_setting_has_exactly_one_complete_profile():
    assert set(PROFILES) == set(LLM_SETTINGS)
    for name, p in PROFILES.items():
        assert p.name == name
        assert len(p.description) > 40
        assert p.min_labs >= 0
        assert p.max_labs is None or p.max_labs >= p.min_labs
        assert p.max_negatives is None or p.max_negatives >= 0
        assert p.stale_rate_multiplier > 0 and p.hedge_rate_multiplier > 0


def test_profiles_encode_the_documented_differences():
    assert PROFILES["ehr_template"].show_flags and PROFILES["ehr_template"].show_ref_ranges
    assert PROFILES["ehr_template"].max_labs is None  # states every non-missing lab
    assert not PROFILES["shorthand"].show_flags
    assert PROFILES["shorthand"].max_labs <= 3 and PROFILES["shorthand"].max_negatives <= 2
    assert PROFILES["ai_scribe"].quote_patient and PROFILES["ai_scribe"].hedge_rate_multiplier > 1
    assert PROFILES["copy_forward"].stale_rate_multiplier > 1
    others = [p.stale_rate_multiplier for n, p in PROFILES.items() if n != "copy_forward"]
    assert PROFILES["copy_forward"].stale_rate_multiplier > max(others)
