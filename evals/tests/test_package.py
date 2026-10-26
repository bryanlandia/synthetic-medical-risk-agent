import pytest

from evals import HARNESS_VERSION
from evals.cli import main


def test_the_package_imports_the_data_generator():
    import data_gen

    assert data_gen.SYNTHETIC_NOTICE and HARNESS_VERSION


def test_the_command_runs_and_states_the_data_is_fictional(capsys):
    assert main([]) == 0
    assert "synthetic" in capsys.readouterr().out.lower()
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0


def test_the_schema_command_prints_the_contract(capsys):
    from evals.report import schema_text

    assert main(["schema"]) == 0
    assert capsys.readouterr().out == schema_text()
