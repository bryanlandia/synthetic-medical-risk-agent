import subprocess
import sys


def test_the_service_carries_no_training_dependencies():
    code = ("import sys, agent.app, agent.runtime, agent.scripted, agent.cli;"
            "bad=[m for m in ('sklearn','scipy','mlflow','pandas','evals','data_gen','training') if m in sys.modules];print(bad)")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", out
