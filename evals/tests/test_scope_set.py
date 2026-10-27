import collections

from evals import scope_set


def test_the_committed_file_is_what_the_module_builds():
    assert scope_set.PATH.read_text() == "".join(__import__("json").dumps(r, sort_keys=True) + "\n" for r in scope_set.build())


def test_every_category_is_present_with_the_expected_behaviour():
    rows = scope_set.load()
    by = collections.Counter(r["category"] for r in rows)
    assert by == {"treatment_request": 14, "real_disease": 10, "phi": 8, "out_of_scope": 12, "legitimate_note": 12, "injected_instruction": 10}
    assert len(rows) == 66 and len({r["id"] for r in rows}) == 66
    for r in rows:
        assert r["expect"] in ("decline", "score") and r["text"].strip()
        assert (r["expect"] == "decline") == (r["reason"] is not None)
        assert r["reason"] in (None, "treatment_request", "real_disease", "phi", "out_of_scope", "other")
        assert ("clean" in r) == (r["category"] == "injected_instruction")


def test_legitimate_notes_mention_medications_and_still_must_be_scored():
    notes = [r for r in scope_set.load() if r["category"] == "legitimate_note"]
    assert sum("medication" in r["text"].lower() or "prescription" in r["text"].lower() for r in notes) >= 10
    assert all(r["expect"] == "score" for r in notes)


def test_injected_prompts_carry_their_clean_twin_and_differ_only_by_the_addendum():
    for r in (r for r in scope_set.load() if r["category"] == "injected_instruction"):
        assert r["text"].startswith(r["clean"]) and "ADDENDUM" in r["text"][len(r["clean"]):] and "ADDENDUM" not in r["clean"]


def test_no_prompt_names_a_real_person_or_a_real_identifier():
    text = " ".join(r["text"] for r in scope_set.load())
    assert "example.com" in text  # placeholders only: a reserved example domain, invented names
