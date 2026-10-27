from data_gen import labs as gen

from risk_model.labs import LABS, SYMPTOM_KEYS


def test_the_lab_copy_matches_the_generators():
    assert [(l.key, l.name, l.abbr, l.unit, l.mean, l.sd, l.ref_lo, l.ref_hi, l.plaus_lo, l.plaus_hi, l.alt_unit, l.factor)
            for l in LABS] == [(l.key, l.name, l.abbr, l.unit, l.mean, l.sd, l.ref_lo, l.ref_hi, l.plaus_lo, l.plaus_hi,
                                l.alt_unit, l.factor) for l in gen.LABS]
    assert SYMPTOM_KEYS == gen.SYMPTOM_KEYS




def test_the_alternate_unit_factors_convert_like_the_generators():
    for lab in LABS:
        if lab.alt_unit:
            assert abs(gen.LAB_BY_KEY[lab.key].to_alt(5.0) - 5.0 * lab.factor) < 1e-12
