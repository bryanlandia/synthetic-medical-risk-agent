import pytest

from risk_model import labvalues as lv
from risk_model.labs import LAB_BY_KEY


def one(note):
    return lv.read(note)


def test_a_result_line_with_abbreviation_and_range():
    [s] = one("- Velorin index (VLI): 129 mg/dL (ref 70-130)")
    assert (s.lab, s.value, s.unit, s.decimals) == ("velorin_index", 129.0, "mg/dL", 0)


def test_an_inline_list_of_values():
    got = one("Velorin index 104 mg/dL, Tarnic acid 220 umol/L, Brell enzyme 34.6 U/L, Dorrin ratio 0.776.")
    assert [(s.lab, s.value) for s in got] == [("velorin_index", 104), ("tarnic_acid", 220), ("brell_enzyme", 34.6),
                                               ("dorrin_ratio", 0.776)]
    assert got[-1].unit is None and got[2].decimals == 1


def test_shorthand_abbreviations_with_and_without_units():
    got = one("K17 3.49, TAC 282, PLX 185. VLI: 83.4 mg/dL")
    assert {(s.lab, s.value) for s in got} == {("serum_k17", 3.49), ("tarnic_acid", 282), ("plexa_count", 185),
                                              ("velorin_index", 83.4)}


def test_prose_forms_of_and_at():
    got = one("including a Velorin index (VLI) of 95.7 mg/dL and a Brell enzyme (BRE) of 39.7 U/L; serum K-17 at 4.49 mmol/L")
    assert [(s.lab, s.value) for s in got] == [("velorin_index", 95.7), ("brell_enzyme", 39.7), ("serum_k17", 4.49)]


def test_an_alternate_unit_is_kept_as_written():
    [s] = one("Serum K-17 (K17) of 15.8 mg/dL")
    assert (s.lab, s.value, s.unit) == ("serum_k17", 15.8, "mg/dL")
    [t] = one("Results: VLI 6.23 mmol/L, ")
    assert t.unit == "mmol/L"


def test_no_values_gives_an_empty_list():
    assert one("Patient denies shaking. Follow up in six weeks.") == []


def test_the_was_reviewed_and_was_form():
    [s] = one("The Dorrin ratio (DOR) was reviewed with the patient and was 0.59.")
    assert (s.lab, s.value, s.unit) == ("dorrin_ratio", 0.59, None)


def test_a_number_that_is_not_adjacent_to_a_lab_name_is_not_read():
    assert one("Velorin index within normal limits. Follow-up in 6 weeks.") == []
    assert one("The Velorin index and Tarnic acid results were reviewed together.") == []


def test_agreement_allows_rounding_and_converts_units():
    k = LAB_BY_KEY["serum_k17"]
    assert lv.agrees(k, lv.Stated("serum_k17", 15.4, "mg/dL", 1), 3.945)       # 3.945 mmol/L x 3.91 = 15.42
    assert not lv.agrees(k, lv.Stated("serum_k17", 15.4, "mg/dL", 1), 4.8)
    v = LAB_BY_KEY["velorin_index"]
    assert lv.agrees(v, lv.Stated("velorin_index", 129.0, "mg/dL", 0), 128.9)  # rounded to a whole number
    assert not lv.agrees(v, lv.Stated("velorin_index", 220.0, "mg/dL", 0), 104.0)

