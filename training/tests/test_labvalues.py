import pytest

from risk_model import labvalues as lv

@pytest.mark.parametrize("setting", ["ehr_template", "shorthand", "ai_scribe", "copy_forward"])
def test_every_stated_value_in_the_train_notes_is_read_for_each_setting(dataset, setting):
    from training import data

    wanted = found = 0
    for r in (r for r in data.training_records(dataset) if r.style == setting):
        got = lv.read(r.input.note)
        for lab in r.plan.labs:
            wanted += 1
            found += any(g.lab == lab.lab and abs(g.value - lab.value) <= max(0.01 * abs(lab.value), 0.5 * 10 ** -g.decimals)
                         for g in got)
    assert found / wanted >= 0.99, (setting, found, wanted)
