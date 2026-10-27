import json
import re

from data_gen.labs import PHRASEBANK, SYMPTOM_KEYS

from training import data, lexicon


def test_terms_are_lowercase_deduplicated_and_belong_to_one_symptom():
    lex = lexicon.build()
    assert set(lex) == set(SYMPTOM_KEYS)
    seen = {}
    for key, terms in lex.items():
        assert terms == sorted(set(terms)) and all(t == t.lower().strip() and t for t in terms)
        for t in terms:
            assert t not in seen, f"{t!r} is in both {seen[t]} and {key}"
            seen[t] = key


def test_every_phrase_the_generator_can_write_is_a_mention_of_its_symptom():
    pats = lexicon.mentions_by_symptom(lexicon.build())
    for key, pools in PHRASEBANK.items():
        for pool in pools.values():
            for phrase in pool:
                assert pats[key].search(phrase.lstrip("?")), f"{phrase!r} is not found as {key}"


def test_the_committed_lexicon_file_is_current():
    assert json.loads(lexicon.LEXICON_PATH.read_text()) == lexicon.build()


def test_almost_every_stated_symptom_in_the_train_notes_has_a_mention(dataset):
    cov = lexicon.coverage(data.training_records(dataset), lexicon.build())
    for key, (found, total) in cov.items():
        assert found / total >= 0.998, (key, found, total)


def test_a_term_matches_only_at_the_start_of_a_word():
    pat = lexicon.pattern(["shak"])
    assert pat.search("hands shaky") and not pat.search("unshaken")
    assert re.search(r"x", "x")
