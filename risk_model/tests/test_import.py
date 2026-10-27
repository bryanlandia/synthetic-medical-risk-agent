import subprocess
import sys


def test_the_package_imports_nothing_heavy():
    code = ("import sys, risk_model, risk_model.reader, risk_model.labvalues, risk_model.features, risk_model.report;"
            "bad=[m for m in ('sklearn','scipy','mlflow','anthropic','pandas','evals','data_gen','training') if m in sys.modules];"
            "print(bad)")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", out
