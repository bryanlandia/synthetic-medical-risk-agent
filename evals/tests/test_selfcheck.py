import pytest

from evals import graders
from evals.selfcheck import self_check
from evals.systems import OracleSystem

from fakes import rec, report, trial


@pytest.fixture(scope="module")
def oracle(dataset):
    return OracleSystem(dataset)


def test_every_grader_scores_the_oracle_as_expected_on_the_real_data(dataset, oracle):
    assert self_check(dataset, oracle) == {}  # and the symptom reading is perfect


def test_the_oracle_reads_every_symptom_correctly(dataset, oracle):
    from evals.harness import run_system

    pairs = list(zip(dataset.by_split["test"], run_system(oracle, dataset.by_split["test"])))
    got = graders.symptom_reading(pairs)
    assert got["accuracy"] == 1.0 and all(v == 1.0 for v in got["per_setting"].values())


def test_a_wrong_grader_is_reported_as_broken_not_as_a_system_failure(dataset, oracle):
    def inverted_borderline(pairs):  # a grader with the bug "uncertain" and "not uncertain" swapped
        real = graders.borderline(pairs)
        return {**real, "borderline_uncertain_rate": 1 - real["borderline_uncertain_rate"],
                "clear_uncertain_rate": 1 - real["clear_uncertain_rate"]}

    def lenient_fabrication(pairs):  # a grader that reports an invented value where there is none
        return {"n": len(pairs), "rate": 0.2, "labs": {}}

    broken = self_check(dataset, oracle, {"borderline": inverted_borderline, "fabrication": lenient_fabrication})
    assert set(broken) == {"borderline", "fabrication"}
    assert "oracle" in broken["borderline"] and "fabricates" in broken["fabrication"]
