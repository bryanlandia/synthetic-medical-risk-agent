import pytest

from evals.records import DEFAULT_DATASET, load_dataset


@pytest.fixture(scope="session")
def dataset():
    if not (DEFAULT_DATASET / "manifest.json").exists():
        pytest.skip("data_gen/data_llm is not present")
    return load_dataset()
