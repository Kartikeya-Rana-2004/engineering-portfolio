import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import numpy as np

FEATURES = ["lag_1", "lag_7", "lag_14", "mean_7", "mean_14", "annual_sin", "annual_cos", "trend_years"] + [f"weekday_{i}" for i in range(6)]
ORIGIN = date(2011, 1, 1)


def feature_vector(target_date, history):
    target = date.fromisoformat(target_date)
    if len(history) != 14:
        raise ValueError("exactly 14 previous daily observations required")
    rows = sorted(history, key=lambda row: row["date"])
    expected = [target - timedelta(days=14-i) for i in range(14)]
    if [date.fromisoformat(row["date"]) for row in rows] != expected:
        raise ValueError("history must contain each preceding day once")
    values = [row["count"] for row in rows]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("counts must be finite nonnegative numbers")
    phase = 2 * math.pi * (target.timetuple().tm_yday - 1) / 365.25
    return np.array([values[-1], values[-7], values[-14], np.mean(values[-7:]), np.mean(values), math.sin(phase), math.cos(phase), (target-ORIGIN).days/365.25] + [int(target.weekday() == i) for i in range(6)], dtype=float)


def read_daily(path):
    with Path(path).open(newline="") as f:
        raw = list(csv.DictReader(f))
    rows = sorted([{"date": row["dteday"], "count": int(row["cnt"])} for row in raw], key=lambda row: row["date"])
    if len(rows) < 200:
        raise ValueError("at least 200 daily records required for temporal evaluation")
    for index, row in enumerate(rows):
        if row["count"] < 0:
            raise ValueError("negative count")
        if index and date.fromisoformat(row["date"]) != date.fromisoformat(rows[index-1]["date"]) + timedelta(days=1):
            raise ValueError("duplicate date or missing day")
    return rows


def design(rows):
    x = np.array([feature_vector(rows[i]["date"], rows[i-14:i]) for i in range(14, len(rows))])
    y = np.array([row["count"] for row in rows[14:]], dtype=float)
    return x, y


def fit(x, y, alpha):
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales == 0] = 1
    z = np.column_stack([np.ones(len(x)), (x-means)/scales])
    penalty = np.eye(z.shape[1]) * alpha
    penalty[0, 0] = 0
    weights = np.linalg.solve(z.T @ z + penalty, z.T @ y)
    return {"features": FEATURES, "means": means.tolist(), "scales": scales.tolist(), "weights": weights.tolist(), "alpha": alpha}


def predict_matrix(model, x):
    z = (x - np.array(model["means"])) / np.array(model["scales"])
    return np.maximum(0, np.column_stack([np.ones(len(x)), z]) @ np.array(model["weights"]))


def metrics(y, prediction):
    return {"mae": round(float(np.mean(np.abs(y-prediction))), 3), "rmse": round(float(np.sqrt(np.mean((y-prediction)**2))), 3)}


def train(path):
    rows = read_daily(path)
    x, y = design(rows)
    n = len(y)
    train_end, validation_end = int(n*0.6), int(n*0.8)
    trials = []
    for alpha in (0.1, 1.0, 10.0, 100.0):
        candidate = fit(x[:train_end], y[:train_end], alpha)
        score = metrics(y[train_end:validation_end], predict_matrix(candidate, x[train_end:validation_end]))
        trials.append({"alpha": alpha, **score})
    chosen = min(trials, key=lambda trial: trial["rmse"])["alpha"]
    model = fit(x[:validation_end], y[:validation_end], chosen)
    model.update({"training_end": rows[14+validation_end-1]["date"], "model_type": "standardized_ridge", "forecast_horizon": "one day ahead with preceding actual observations"})
    identity = hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()[:16]
    model["model_id"] = identity
    actual = y[validation_end:]
    predictions = predict_matrix(model, x[validation_end:])
    test_rows = rows[14+validation_end:]
    evidence = {"source": "UCI Bike Sharing, daily counts, 2011–2012", "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "source_rows": len(rows), "usable_rows": n, "split": {"train": train_end, "validation": validation_end-train_end, "test": n-validation_end},
                "test_start": test_rows[0]["date"], "test_end": test_rows[-1]["date"], "validation_trials": trials,
                "selected_alpha": chosen, "test": {"ridge": metrics(actual, predictions), "yesterday": metrics(actual, x[validation_end:,0]), "same_weekday_last_week": metrics(actual, x[validation_end:,1])},
                "protocol": "chronological split; hyperparameters selected on validation; final fit uses train+validation; rolling one-day-ahead test uses earlier actual observations, including earlier test days",
                "excluded_fields": ["casual", "registered", "same_day_cnt", "same_day_weather", "same_day_temperature"], "model_id": identity}
    evidence["test_predictions"] = [{"date": row["date"], "actual": row["count"], "predicted": round(float(pred),3)} for row,pred in zip(test_rows,predictions)]
    return model, evidence


def predict(model, payload):
    if not isinstance(payload, dict) or set(payload) != {"target_date", "history"}:
        raise ValueError("target_date and history required; unknown fields rejected")
    if not isinstance(payload["history"], list):
        raise ValueError("history must be an array")
    vector = feature_vector(payload["target_date"], payload["history"])
    target = date.fromisoformat(payload["target_date"])
    last = date.fromisoformat(model["training_end"])
    if not last < target <= last + timedelta(days=366):
        raise ValueError("prediction date must follow training and be within 366 days; retrain for later dates")
    prediction = float(predict_matrix(model, vector[None,:])[0])
    return {"model_id": model["model_id"], "target_date": payload["target_date"], "predicted_count": round(prediction,3), "training_end": model["training_end"], "horizon": "one-day-ahead"}
