#!/usr/bin/env python3
"""Leakage-safe time-split forecast baselines for the 2024-2026 synthetic pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = actual.astype(float)
    predicted = np.maximum(0.0, predicted.astype(float))
    error = predicted - actual
    denominator = np.abs(actual) + np.abs(predicted)
    smape = np.mean(np.divide(2.0 * np.abs(error), denominator, out=np.zeros_like(error), where=denominator > 0))
    total_actual = float(np.abs(actual).sum())
    variance = float(((actual - actual.mean()) ** 2).sum())
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "smape": float(smape),
        "wape": float(np.abs(error).sum() / total_actual) if total_actual else 0.0,
        "r2": float(1.0 - (error**2).sum() / variance) if variance else 0.0,
    }


def _calendar_matrix(frame: pd.DataFrame, hubs: list[str], origin: pd.Timestamp) -> np.ndarray:
    date = frame["date"]
    columns: list[np.ndarray] = [np.ones(len(frame), dtype=float)]
    elapsed = (date - origin).dt.days.to_numpy(dtype=float) / 1096.0
    columns.append(elapsed)
    angle = 2.0 * np.pi * (date.dt.month.to_numpy(dtype=float) - 1.0) / 12.0
    columns.extend([np.sin(angle), np.cos(angle), np.sin(2 * angle), np.cos(2 * angle)])
    dow = date.dt.dayofweek.to_numpy()
    for value in range(1, 7):
        columns.append((dow == value).astype(float))
    for hub in hubs[1:]:
        columns.append((frame["hub_id"].to_numpy() == hub).astype(float))
    return np.column_stack(columns)


def evaluate(orders_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    orders = pd.read_csv(orders_path)
    orders["date"] = pd.to_datetime(orders["arrival_ts"]).dt.tz_localize(None).dt.floor("D")
    observed = orders.groupby(["date", "hub_id"], as_index=False).size().rename(columns={"size": "actual_orders"})
    hubs = sorted(observed["hub_id"].unique())
    dates = pd.date_range(observed["date"].min(), observed["date"].max(), freq="D")
    full = pd.MultiIndex.from_product([dates, hubs], names=["date", "hub_id"]).to_frame(index=False)
    full = full.merge(observed, on=["date", "hub_id"], how="left")
    full["actual_orders"] = full["actual_orders"].fillna(0.0)
    train = full[full["date"] < pd.Timestamp("2026-01-01")].copy()
    test = full[full["date"] >= pd.Timestamp("2026-01-01")].copy()

    monthly_mean = train.groupby(["hub_id", train["date"].dt.month])["actual_orders"].mean()
    fallback = train.groupby("hub_id")["actual_orders"].mean().to_dict()
    test["monthly_seasonal"] = [
        float(monthly_mean.get((hub, date.month), fallback[hub]))
        for date, hub in zip(test["date"], test["hub_id"])
    ]

    previous_year = full.assign(
        month=full["date"].dt.month,
        day=full["date"].dt.day,
        year=full["date"].dt.year,
    ).set_index(["year", "month", "day", "hub_id"])["actual_orders"]
    seasonal_naive = []
    for date, hub in zip(test["date"], test["hub_id"]):
        value = previous_year.get((date.year - 1, date.month, date.day, hub))
        if value is None or pd.isna(value):
            value = monthly_mean.get((hub, date.month), fallback[hub])
        seasonal_naive.append(float(value))
    test["seasonal_naive"] = seasonal_naive

    rolling = (
        full.sort_values(["hub_id", "date"])
        .groupby("hub_id")["actual_orders"]
        .transform(lambda values: values.shift(1).rolling(28, min_periods=7).mean())
    )
    full["rolling_28d"] = rolling
    test = test.merge(full[["date", "hub_id", "rolling_28d"]], on=["date", "hub_id"], how="left")
    test["rolling_28d"] = test["rolling_28d"].fillna(test["monthly_seasonal"])

    origin = full["date"].min()
    x_train = _calendar_matrix(train, hubs, origin)
    x_test = _calendar_matrix(test, hubs, origin)
    y_train = train["actual_orders"].to_numpy(dtype=float)
    ridge = np.eye(x_train.shape[1], dtype=float) * 4.0
    ridge[0, 0] = 0.0
    beta = np.linalg.solve(x_train.T @ x_train + ridge, x_train.T @ y_train)
    test["calendar_trend_ridge"] = np.maximum(0.0, x_test @ beta)

    models = ["seasonal_naive", "rolling_28d", "monthly_seasonal", "calendar_trend_ridge"]
    rows: list[dict[str, object]] = []
    for model in models:
        scopes = [("all_hubs", test)] + [
            (hub, test[test["hub_id"] == hub]) for hub in hubs
        ]
        for scope, subset in scopes:
            result = _metrics(
                subset["actual_orders"].to_numpy(dtype=float),
                subset[model].to_numpy(dtype=float),
            )
            rows.append(
                {
                    "model": model,
                    "scope": scope,
                    "grain": "daily_hub",
                    "n_observations": int(len(subset)),
                    **result,
                }
            )
    metrics = pd.DataFrame(rows)

    monthly = test.copy()
    monthly["month"] = monthly["date"].dt.strftime("%Y-%m")
    predictions = (
        monthly.groupby(["month", "hub_id"], as_index=False)[
            ["actual_orders", *models]
        ]
        .sum()
        .sort_values(["month", "hub_id"])
    )
    for model in models:
        rows.append(
            {
                "model": model,
                "scope": "all_hubs",
                "grain": "monthly_hub",
                "n_observations": int(len(predictions)),
                **_metrics(
                    predictions["actual_orders"].to_numpy(dtype=float),
                    predictions[model].to_numpy(dtype=float),
                ),
            }
        )
    metrics = pd.DataFrame(rows)
    metadata = {
        "train_period": {"start": "2024-01-01", "end": "2025-12-31"},
        "test_period": {"start": "2026-01-01", "end": "2026-12-31"},
        "split_type": "strict_time_split",
        "random_split_used": False,
        "rolling_28d_policy": "one-step baseline using observed history available before each prediction day",
        "label_leakage_fields": [],
        "models": models,
    }
    return metrics, predictions, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", default="data/generated/three_year/csv/orders.csv")
    parser.add_argument("--output-dir", default="data/generated/three_year/analytics")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics, predictions, metadata = evaluate(Path(args.orders))
    metrics.to_csv(output_dir / "forecast_evaluation.csv", index=False, lineterminator="\n", float_format="%.6f")
    predictions.to_csv(output_dir / "forecast_predictions_2026.csv", index=False, lineterminator="\n", float_format="%.6f")
    (output_dir / "forecast_evaluation_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pack_metadata_path = output_dir.parent / "metadata.json"
    if pack_metadata_path.exists():
        pack_metadata = json.loads(pack_metadata_path.read_text(encoding="utf-8"))
        analytics_files = pack_metadata.setdefault("analytics_files", {})
        for filename in (
            "forecast_evaluation.csv",
            "forecast_predictions_2026.csv",
            "forecast_evaluation_metadata.json",
        ):
            path = output_dir / filename
            analytics_files[f"analytics/{filename}"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        pack_metadata_path.write_text(
            json.dumps(pack_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(metrics[metrics["scope"] == "all_hubs"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
