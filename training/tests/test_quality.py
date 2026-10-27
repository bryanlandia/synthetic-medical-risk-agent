from pathlib import Path

from evals.graders import true_warning_types
from evals.records import input_view

import risk_model
from training import data


def test_data_quality_on_the_train_records_matches_the_labels(dataset):
    model = risk_model.load(Path(__file__).resolve().parents[1] / "model")
    recs = data.training_records(dataset)[:800]
    stats = {t: [0, 0, 0] for t in ("missing_value", "unit_mismatch", "contradiction")}
    for r in recs:
        said = {w["type"] for w in model.report(input_view(r))["data_quality"]}
        truth = true_warning_types(r)
        for t in stats:
            stats[t][0] += t in truth
            stats[t][1] += t in said
            stats[t][2] += t in truth and t in said
    for t, (has, warned, both) in stats.items():
        assert has > 20, t
        assert both / has >= 0.95, (t, "recall", both, has)
        assert both / warned >= 0.97, (t, "precision", both, warned)
