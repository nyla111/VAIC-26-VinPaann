"""Train một model học máy thật cho phần "predicted unknown future load" của forecast.

Chạy:
    cd VAIC-26-VinPaann
    python -m ai2_dispatch.scripts.train_forecaster
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from ai2_dispatch.app.enums import Mode
from ai2_dispatch.scripts.simulate_and_tune import load_ct_bound_shipments

BUCKET_MINUTES = 30
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_PATH = MODEL_DIR / "arrival_forecaster.joblib"
METRICS_PATH = MODEL_DIR / "training_metrics.json"

FEATURE_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "month",
    "is_water",
    "lag_count_1",
    "lag_count_2",
    "rolling_count_3",
    "rolling_weight_3",
]


def _floor_bucket(ts: datetime) -> datetime:
    minute = (ts.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return ts.replace(minute=minute, second=0, microsecond=0)


def build_bucket_frame(month_prefixes: tuple[str, ...] = ("2026-01", "2026-05", "2026-09")) -> pd.DataFrame:
    """Bucket 30 phút theo `(outbound_mode, tháng)` từ shipment thật "đi qua Cần Thơ" — cùng
    nguồn với `simulate_and_tune.load_ct_bound_shipments()`."""

    shipments = load_ct_bound_shipments(month_prefixes)

    by_month_mode: dict[tuple[str, Mode], list] = defaultdict(list)
    for s in shipments:
        by_month_mode[(s.eta_can_tho.strftime("%Y-%m"), s.outbound_mode)].append(s)

    rows = []
    for (_month_key, mode), group in by_month_mode.items():
        start = min(s.eta_can_tho for s in group).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = max(s.eta_can_tho for s in group) + timedelta(days=1)
        bucket_index = pd.date_range(start, end, freq=f"{BUCKET_MINUTES}min", inclusive="left")

        weight_by_bucket = {b: 0.0 for b in bucket_index}
        count_by_bucket = {b: 0 for b in bucket_index}
        for s in group:
            b = _floor_bucket(s.eta_can_tho)
            if b in weight_by_bucket:
                weight_by_bucket[b] += s.weight_kg
                count_by_bucket[b] += 1

        weights = [weight_by_bucket[b] for b in bucket_index]
        counts = [count_by_bucket[b] for b in bucket_index]

        for i, b in enumerate(bucket_index):
            lag1 = counts[i - 1] if i >= 1 else 0
            lag2 = counts[i - 2] if i >= 2 else 0
            count_window = counts[max(0, i - 3) : i]
            weight_window = weights[max(0, i - 3) : i]
            rows.append(
                {
                    "bucket_start": b,
                    "outbound_mode": mode.value,
                    "is_water": 1 if mode == Mode.WATER else 0,
                    "hour_of_day": b.hour,
                    "day_of_week": b.weekday(),
                    "month": b.month,
                    "lag_count_1": lag1,
                    "lag_count_2": lag2,
                    "rolling_count_3": sum(count_window) / len(count_window) if count_window else 0.0,
                    "rolling_weight_3": sum(weight_window) / len(weight_window) if weight_window else 0.0,
                    "target_weight_kg": weights[i],
                }
            )

    return pd.DataFrame(rows).sort_values("bucket_start").reset_index(drop=True)


def train_and_evaluate(frame: pd.DataFrame):
    split = int(len(frame) * 0.8)
    train, test = frame.iloc[:split], frame.iloc[split:]

    model = GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model.fit(train[FEATURE_COLUMNS], train["target_weight_kg"])

    pred_test = np.clip(model.predict(test[FEATURE_COLUMNS]), 0, None)
    mae_model = mean_absolute_error(test["target_weight_kg"], pred_test)
    mae_baseline = mean_absolute_error(test["target_weight_kg"], test["rolling_weight_3"])

    metrics = {
        "trained_at": datetime.now().isoformat(),
        "n_rows_total": len(frame),
        "n_rows_train": len(train),
        "n_rows_test": len(test),
        "mae_model_kg": round(float(mae_model), 2),
        "mae_rolling_mean_baseline_kg": round(float(mae_baseline), 2),
        "model_better_than_baseline": bool(mae_model < mae_baseline),
        "feature_columns": FEATURE_COLUMNS,
        "note": (
            "Sample nhỏ (3 tháng, arrival thưa vì chỉ ~7% order đi qua Cần Thơ theo per-order "
            "routing)."
        ),
    }
    return model, metrics


def main() -> None:
    print("Building bucket-level training data from real canonical orders...")
    frame = build_bucket_frame()
    print(f"  {len(frame)} bucket rows, {frame['target_weight_kg'].gt(0).sum()} non-zero buckets.")

    print("Training GradientBoostingRegressor...")
    model, metrics = train_and_evaluate(frame)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Metrics saved to {METRICS_PATH}")


if __name__ == "__main__":
    main()
