import pytest

from training import data


def test_training_records_are_exactly_the_train_ids(dataset):
    from evals.devsplit import dev_ids, train_ids

    recs = data.training_records(dataset)
    assert [r.patient_id for r in recs] == train_ids(dataset)
    assert not {r.patient_id for r in recs} & set(dev_ids(dataset))
    assert all(r.split == "train" for r in recs) and len(recs) + 500 == len(dataset.by_split["train"])


@pytest.mark.parametrize("split", ["test", "adversarial"])
def test_a_protected_split_record_is_refused_by_id(dataset, split):
    rec = dataset.by_split[split][0]
    with pytest.raises(data.ProtectedRecordError, match=rec.patient_id):
        data.assert_trainable(dataset, [*data.training_records(dataset)[:3], rec])


def test_a_dev_record_is_refused_by_id(dataset):
    rec = data.dev_records(dataset)[0]
    with pytest.raises(data.ProtectedRecordError, match=rec.patient_id):
        data.assert_trainable(dataset, [rec])


def test_the_training_set_passes_its_own_check(dataset):
    data.assert_trainable(dataset, data.training_records(dataset))
