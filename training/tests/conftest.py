import pytest

from training import data


@pytest.fixture(scope="session")
def dataset():
    return data.load()
