import numpy as np
import pytest

from evals.devsplit import dev_ids
from evals.harness import run_system, run_trial
from evals.metrics import auc, brier, ece, log_loss
from evals.records import input_view, unique_patients
from evals.report import SYMPTOM_READINGS, parse_report
from evals.systems import FloorSystem, LabOnlySystem, OracleSystem


@pytest.fixture(scope="module")
def systems(dataset):
    return OracleSystem(dataset), FloorSystem(dataset), LabOnlySystem(dataset)


def sample(dataset, split, n=60):
    return dataset.by_split[split][:n]


def test_every_reference_system_returns_valid_reports_on_every_split(dataset, systems):
    for system in systems:
        assert system.reference and system.version.endswith("@1")
        for split in ("train", "test", "adversarial"):
            for record in sample(dataset, split):
                result = parse_report(system.run(input_view(record)))
                assert result.ok, (system.name, result.errors)
                assert result.report.disclaimer


def test_systems_receive_only_the_view(dataset, systems):
    seen = []

    class Spy:
        name, version, reference = "spy", "spy@1", False

        def run(self, view):
            seen.append(sorted(view))
            return systems[1].run(view)

    run_system(Spy(), sample(dataset, "test", 5))
    assert seen == [["note", "panel", "patient_id"]] * 5


def test_the_oracle_reads_symptoms_warnings_and_uncertainty_from_the_truth(dataset, systems):
    oracle = systems[0]
    for record in dataset.by_split["adversarial"]:
        report = parse_report(oracle.run(input_view(record))).report
        assert report.probability == record.ground_truth.true_probability
        assert report.uncertain == (0.4 <= report.probability <= 0.6)
        types = {w.type for w in report.data_quality}
        for tag in record.tags:
            if tag.type in {"impossible_value", "note_flag_disagreement", "unit_mismatch", "contradiction"}:
                assert tag.type in types
    record = next(r for r in dataset.by_split["test"] if r.plan and any(s.stated == "hedged" for s in r.plan.symptoms))
    report = parse_report(oracle.run(input_view(record))).report
    hedged = next(s.flag for s in record.plan.symptoms if s.stated == "hedged")
    assert report.symptoms[hedged] == "possible" and set(report.symptoms.values()) <= set(SYMPTOM_READINGS)


def test_the_floor_reports_the_training_prevalence_and_reads_nothing(dataset, systems):
    floor = systems[1]
    report = parse_report(floor.run(input_view(dataset.by_split["test"][0]))).report
    assert report.probability == pytest.approx(floor.prevalence) and set(report.symptoms.values()) == {"not_mentioned"}
    assert report.data_quality == [] and report.uncertain is False


def test_the_lab_only_baseline_is_deterministic_and_fit_without_dev(dataset):
    a, b = LabOnlySystem(dataset), LabOnlySystem(dataset)
    assert np.allclose(a.weights, b.weights) and a.n_fit == len(dataset.by_split["train"]) - 500


# --- 3.3 the harness against the real data -----------------------------------------------------------------------

def scores(dataset, system, records):
    trials = run_system(system, records)
    assert all(t.parsed for t in trials)
    y = np.array([r.ground_truth.label for r in records], dtype=float)
    p = np.array([t.report.probability for t in trials])
    return {"auc": auc(y, p), "brier": brier(y, p), "log_loss": log_loss(y, p), "ece": ece(y, p)}, y


def test_the_oracle_reaches_the_manifest_ceiling_on_test(dataset, systems):
    got, _ = scores(dataset, systems[0], unique_patients(dataset.by_split["test"]))  # one record per patient
    ceiling = dataset.manifest["splits"]["test"]["bayes_ceiling"]
    for metric in ("auc", "brier", "log_loss"):
        assert abs(got[metric] - ceiling[metric]) <= 0.0005, (metric, got[metric], ceiling[metric])


def test_counting_every_matched_pair_record_would_not_match_the_ceiling(dataset, systems):
    all_records, _ = scores(dataset, systems[0], dataset.by_split["test"])
    ceiling = dataset.manifest["splits"]["test"]["bayes_ceiling"]
    assert abs(all_records["auc"] - ceiling["auc"]) > 0.002  # which is why metrics use one record per patient


def test_the_oracle_reaches_the_ceiling_on_adversarial_too(dataset, systems):
    got, _ = scores(dataset, systems[0], unique_patients(dataset.by_split["adversarial"]))
    ceiling = dataset.manifest["splits"]["adversarial"]["bayes_ceiling"]
    assert all(abs(got[m] - ceiling[m]) <= 0.0005 for m in ("auc", "brier", "log_loss"))


def test_the_floor_sits_at_the_floor(dataset, systems):
    got, y = scores(dataset, systems[1], unique_patients(dataset.by_split["test"]))
    prevalence = y.mean()
    assert got["auc"] == 0.5
    assert abs(got["brier"] - prevalence * (1 - prevalence)) <= 0.002


def test_the_lab_only_baseline_lies_between_the_floor_and_the_oracle(dataset, systems):
    dev = set(dev_ids(dataset))
    records = [r for r in dataset.by_split["train"] if r.patient_id in dev]
    lab, _ = scores(dataset, systems[2], records)
    oracle, _ = scores(dataset, systems[0], records)
    floor, _ = scores(dataset, systems[1], records)
    assert 0.55 < lab["auc"] < oracle["auc"]
    assert oracle["brier"] < lab["brier"] < floor["brier"] + 0.01  # better than guessing, worse than the oracle
