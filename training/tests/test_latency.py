from pathlib import Path

from training import latency

MODEL = Path(__file__).resolve().parents[1] / "model"


def test_the_model_is_small_and_one_report_is_fast_on_one_thread(dataset):
    res = latency.measure(MODEL, dataset, n=120)
    assert res["threads"] == 1 and res["records"] == 120
    assert res["model_bytes"] < 10_000_000
    assert res["p95_ms"] < 100.0 and res["median_ms"] <= res["p95_ms"]
    assert res["meets_limits"]
