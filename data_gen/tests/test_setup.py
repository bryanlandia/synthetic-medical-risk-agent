from pathlib import Path

import data_gen


def test_package_imports_with_versions():
    assert data_gen.GENERATOR_VERSION
    assert data_gen.SCHEMA_VERSION


def test_readme_states_synthetic_and_fictional():
    readme = (Path(__file__).parent.parent / "README.md").read_text().lower()
    assert "synthetic" in readme
    assert "fictional" in readme
    assert "medical" in readme
