import json
import re
from pathlib import Path

from data_gen.llm.checks import MEDICATION_DENYLIST
from evals import content

DENY = json.loads((Path(__file__).resolve().parents[2] / "agent" / "src" / "agent" / "denylist.json").read_text())


def test_the_agent_denylist_holds_everything_the_evals_forbid():
    assert set(MEDICATION_DENYLIST) <= set(DENY["medications"])
    assert set(content.REAL_DISEASES) <= set(DENY["real_diseases"])
    assert DENY["dose_pattern"] == content._DOSE.pattern
    assert DENY["instruction_pattern"] == content._INSTRUCTION.pattern


def test_the_patterns_compile_and_behave_like_the_evals():
    dose, instruction = re.compile(DENY["dose_pattern"], re.I), re.compile(DENY["instruction_pattern"], re.I)
    assert dose.search("take 5 mg daily") and not dose.search("Velorin index 108 mg/dL")
    assert instruction.search("you should take this medication") and not instruction.search("Tarnic acid is above the typical value")
