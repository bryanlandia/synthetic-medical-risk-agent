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



# --- commas: a decimal comma, a thousands separator, or an ambiguous one ---------------------------------------------------------

from risk_model.labs import LAB_BY_KEY  # noqa: E402


@pytest.mark.parametrize("token,lab,unit,expected", [
    ("0,98", "dorrin_ratio", None, (0.98, 2)),
    ("108,5", "velorin_index", "mg/dL", (108.5, 1)),
    ("3,5", "halvin_titer", "g/dL", (3.5, 1)),
    ("4,082", "serum_k17", "mmol/L", (4.082, 3)),            # thousands form, but 4082 is impossible and 4.082 is not
    ("1,040", "tarnic_acid", "umol/L", (1040.0, 0)),         # neither reading is possible: passed on as written
    ("1.250,5", "plexa_count", "x10^9/L", (1250.5, 1)),      # both separators: the last is the decimal point
    ("1,234,567", "velorin_index", "mg/dL", (1234567.0, 0)),
    ("128.9", "velorin_index", "mg/dL", (128.9, 1)),
    ("-5", "velorin_index", "mg/dL", (-5.0, 0)),
])
def test_resolve_reads_commas_by_what_a_patient_could_have(token, lab, unit, expected):
    assert lv.resolve(token, LAB_BY_KEY[lab], unit) == pytest.approx(expected)


@pytest.mark.parametrize("token", ["1.2.3", "1,2,3", "12,34,567", "--5"])
def test_resolve_leaves_out_a_number_it_cannot_read(token):
    assert lv.resolve(token, LAB_BY_KEY["velorin_index"], "mg/dL") is None


def test_an_ambiguous_comma_where_both_readings_are_possible_is_left_out():
    class Wide:  # a lab whose plausible range covers both 1.5 and 1500
        plaus_lo, plaus_hi, alt_unit, factor = 0.0, 10_000.0, None, None

        def to_usual(self, value, unit):
            return value

    assert lv.resolve("1,500", Wide(), None) is None


def test_a_range_is_still_not_a_reading_and_a_trailing_full_stop_is_fine():
    assert lv.read("Velorin index 70-130 mg/dL") == []
    [s] = lv.read("Velorin index 108.")
    assert s.value == 108.0


def test_the_unit_after_a_comma_number_is_still_read():
    [s] = lv.read("Serum K-17 15,4 mg/dL")
    assert (s.value, s.unit, s.decimals) == (15.4, "mg/dL", 1)
