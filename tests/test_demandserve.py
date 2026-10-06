import copy
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from demandserve.model import FEATURES, feature_vector, fit, metrics, predict, predict_matrix, train

ROOT = Path(__file__).resolve().parents[1]


def history(target):
    start = date.fromisoformat(target) - timedelta(days=14)
    return [{"date": (start+timedelta(days=i)).isoformat(), "count": 100+i} for i in range(14)]


class ModelTests(unittest.TestCase):
    def test_uses_only_preceding_observations(self):
        vector = feature_vector("2012-10-01", history("2012-10-01"))
        self.assertEqual(vector[0], 113)
        self.assertEqual(vector[1], 107)
        self.assertEqual(vector[2], 100)
        self.assertEqual(len(vector), len(FEATURES))

    def test_rejects_missing_date(self):
        rows = history("2012-10-01")
        rows[-1]["date"] = "2012-10-01"
        with self.assertRaises(ValueError):
            feature_vector("2012-10-01", rows)

    def test_rejects_duplicate_day(self):
        rows = history("2012-10-01")
        rows[-1] = rows[0]
        with self.assertRaises(ValueError):
            feature_vector("2012-10-01", rows)

    def test_rejects_nonfinite_count(self):
        rows = history("2012-10-01")
        rows[0]["count"] = float("nan")
        with self.assertRaises(ValueError):
            feature_vector("2012-10-01", rows)

    def test_standardization_uses_only_fit_subset(self):
        x = np.array([[1, 2], [3, 4]], dtype=float)
        model = fit(x, np.array([10, 20]), 1)
        self.assertEqual(model["means"], [2, 3])

    def test_constant_columns_are_supported(self):
        model = fit(np.ones((10, 2)), np.ones(10)*3, 1)
        prediction = predict_matrix(model, np.ones((1, 2)))
        self.assertAlmostEqual(prediction[0], 3)

    def test_model_artifact_prediction(self):
        model = json.loads((ROOT / "models/demandserve.json").read_text())
        result = predict(model, {"target_date": "2012-10-01", "history": history("2012-10-01")})
        self.assertGreaterEqual(result["predicted_count"], 0)
        self.assertEqual(result["model_id"], model["model_id"])

    def test_rejects_stale_model_for_far_future(self):
        model = json.loads((ROOT / "models/demandserve.json").read_text())
        with self.assertRaises(ValueError):
            predict(model, {"target_date": "2026-10-01", "history": history("2026-10-01")})

    def test_rejects_leakage_field_in_api(self):
        model = json.loads((ROOT / "models/demandserve.json").read_text())
        with self.assertRaises(ValueError):
            predict(model, {"target_date": "2012-10-01", "history": history("2012-10-01"), "cnt": 500})

    def test_test_targets_cannot_change_fitted_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "daily.csv"
            start = date(2011, 1, 1)
            rows = [{"dteday": (start+timedelta(days=i)).isoformat(), "cnt": 100+i%7+i} for i in range(250)]
            def write():
                with path.open("w", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=["dteday", "cnt"])
                    writer.writeheader()
                    writer.writerows(rows)
            write()
            original, report = train(path)
            test_start = report["test_start"]
            for row in rows:
                if row["dteday"] >= test_start:
                    row["cnt"] += 50000
            write()
            changed, _ = train(path)
            self.assertEqual(original, changed)

    def test_metrics(self):
        self.assertEqual(metrics(np.array([0., 2.]), np.array([1., 1.])), {"mae": 1., "rmse": 1.})


if __name__ == "__main__":
    unittest.main()
