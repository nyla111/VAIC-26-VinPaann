"""Forecast — hybrid:

    forecasted_cumulative_load
        = current_arrived_load          (chắc chắn, từ state_store)
        + known_inbound_load_by_eta     (chắc chắn, từ event shipment_routed)
        + predicted_unknown_future_load (model)

`predicted_unknown_future_load`:
- Nếu đã chạy `scripts/train_forecaster.py` và artifact tồn tại
  (`models/arrival_forecaster.joblib`): dùng model đã train (GradientBoostingRegressor, train
  trên bucket thật từ `orders.csv` canonical — xem script đó), điều kiện theo giờ trong
  ngày/ngày trong tuần/tháng/outbound_mode + lag/rolling feature từ lịch sử arrival thật của
  service.
- Nếu chưa train (chưa chạy script, hoặc thiếu sklearn lúc runtime): fallback về rolling-mean
  toàn cục quan sát được (`state_store.rolling_mean_kg_per_bucket()`). Service không bao giờ crash vì thiếu model optional.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from . import ml_forecaster
from .enums import Mode
from .state_store import StateStore, Vehicle

ML_MODEL_NAME = "gradient_boosting_arrival_forecaster_v1"
ROLLING_MEAN_MODEL_NAME = "rolling_mean_v1"


@dataclass
class ForecastBucketResult:
    timestamp: datetime
    known_inbound_kg: float
    predicted_unknown_kg: float
    predicted_cumulative_load_kg: float


@dataclass
class ForecastResult:
    generated_at: datetime
    bucket_minutes: int
    horizon_hours: int
    current_load_kg: float
    buckets: list[ForecastBucketResult]
    predicted_full_load_time: Optional[datetime]
    predicted_load_kg: Optional[float]
    target_vehicle: Optional[Vehicle]
    confidence: float
    model_name: str


def _floor_to_bucket(ts: datetime, bucket_minutes: int) -> datetime:
    minute = (ts.minute // bucket_minutes) * bucket_minutes
    return ts.replace(minute=minute, second=0, microsecond=0)


def _lag_features_from_history(store: StateStore, lookback: int = 10) -> dict[str, float]:
    """Feature lag/rolling tính từ lịch sử arrival THẬT của service (không phải từ
    training data) — giữ tĩnh xuyên suốt horizon dự báo (không đệ quy cập nhật theo từng
    bucket dự đoán), đơn giản hoá có chủ đích cho v1."""

    history = store.arrival_history[-lookback:]
    if not history:
        return {"lag_count_1": 0, "lag_count_2": 0, "rolling_count_3": 0.0, "rolling_weight_3": 0.0}

    weight_by_bucket: dict[datetime, float] = defaultdict(float)
    count_by_bucket: dict[datetime, int] = defaultdict(int)
    for obs in history:
        weight_by_bucket[obs.bucket_start] += obs.weight_kg
        count_by_bucket[obs.bucket_start] += 1

    buckets_sorted = sorted(weight_by_bucket)
    counts = [count_by_bucket[b] for b in buckets_sorted]
    weights = [weight_by_bucket[b] for b in buckets_sorted]
    return {
        "lag_count_1": counts[-1] if counts else 0,
        "lag_count_2": counts[-2] if len(counts) >= 2 else 0,
        "rolling_count_3": sum(counts[-3:]) / len(counts[-3:]) if counts else 0.0,
        "rolling_weight_3": sum(weights[-3:]) / len(weights[-3:]) if weights else 0.0,
    }


def build_forecast(
    store: StateStore,
    decision_ts: datetime,
    outbound_mode: Mode,
    bucket_minutes: int = 30,
    horizon_hours: int = 6,
    target_vehicle: Optional[Vehicle] = None,
) -> ForecastResult:
    current_load_kg = sum(s.effective_weight_kg for s in store.pending_shipments(outbound_mode))

    n_buckets = int(horizon_hours * 60 / bucket_minutes)
    bucket_starts = [
        _floor_to_bucket(decision_ts, bucket_minutes) + timedelta(minutes=bucket_minutes * (i + 1))
        for i in range(n_buckets)
    ]

    known_by_bucket: dict[datetime, float] = {ts: 0.0 for ts in bucket_starts}
    for shipment in store.in_transit_shipments(outbound_mode):
        bucket = _floor_to_bucket(shipment.eta_can_tho, bucket_minutes)
        if bucket in known_by_bucket:
            known_by_bucket[bucket] += shipment.weight_kg

    model_bundle = ml_forecaster.load_model_bundle()
    if model_bundle is not None:
        model_name = ML_MODEL_NAME
        lag_features = _lag_features_from_history(store)
    else:
        model_name = ROLLING_MEAN_MODEL_NAME
        unknown_per_bucket = store.rolling_mean_kg_per_bucket()

    buckets: list[ForecastBucketResult] = []
    cumulative = current_load_kg
    for ts in bucket_starts:
        known = known_by_bucket[ts]
        if model_bundle is not None:
            features = {
                "hour_of_day": ts.hour,
                "day_of_week": ts.weekday(),
                "month": ts.month,
                "is_water": 1 if outbound_mode == Mode.WATER else 0,
                **lag_features,
            }
            unknown = ml_forecaster.predict_bucket_weight(model_bundle, features)
        else:
            unknown = unknown_per_bucket
        cumulative += known + unknown
        buckets.append(
            ForecastBucketResult(
                timestamp=ts,
                known_inbound_kg=known,
                predicted_unknown_kg=unknown,
                predicted_cumulative_load_kg=round(cumulative, 2),
            )
        )

    predicted_full_load_time: Optional[datetime] = None
    predicted_load_kg: Optional[float] = None
    if target_vehicle is not None:
        threshold = target_vehicle.capacity_kg
        if current_load_kg >= threshold:
            predicted_full_load_time = decision_ts
            predicted_load_kg = current_load_kg
        else:
            for bucket in buckets:
                if bucket.predicted_cumulative_load_kg >= threshold:
                    predicted_full_load_time = bucket.timestamp
                    predicted_load_kg = bucket.predicted_cumulative_load_kg
                    break

    # Confidence thô: tăng dần theo số quan sát thật đã tích lũy
    confidence = round(min(0.35 + 0.05 * store.observation_count(), 0.85), 4)

    return ForecastResult(
        generated_at=decision_ts,
        bucket_minutes=bucket_minutes,
        horizon_hours=horizon_hours,
        current_load_kg=round(current_load_kg, 2),
        buckets=buckets,
        predicted_full_load_time=predicted_full_load_time,
        predicted_load_kg=predicted_load_kg,
        target_vehicle=target_vehicle,
        confidence=confidence,
        model_name=model_name,
    )
