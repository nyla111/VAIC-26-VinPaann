"""Forecast v1 — rolling-mean baseline, KHÔNG dùng model đã train trong
VAIC_Phase2_Rolling_Forecaster.ipynb (notebook đó train trên dataset simulate riêng của AI2,
chưa finalize trên canonical data thật — xem README mục "Điểm khác với AI2-plan.pdf").

Kiến trúc vẫn đúng theo AI2-plan.pdf mục 3.3 (hybrid):

    forecasted_cumulative_load
        = current_arrived_load          (chắc chắn, từ state_store)
        + known_inbound_load_by_eta     (chắc chắn, từ event shipment_routed)
        + predicted_unknown_future_load (model — v1 dùng rolling mean quan sát được)

`predicted_unknown_future_load` v1 = hằng số/bucket lấy từ `state_store.rolling_mean_kg_per_bucket()`.
Đây chính là "baseline bắt buộc" (RollingMeanForecaster) trong AI2-plan.pdf mục 3.3 — không
phải một shortcut tự chế; PoissonArrivalForecaster / model học từ Phase 2 notebook có thể thay
thế sau khi có đủ event log thật (xem README phần roadmap).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .enums import Mode
from .state_store import StateStore, Vehicle


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


def _floor_to_bucket(ts: datetime, bucket_minutes: int) -> datetime:
    minute = (ts.minute // bucket_minutes) * bucket_minutes
    return ts.replace(minute=minute, second=0, microsecond=0)


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

    unknown_per_bucket = store.rolling_mean_kg_per_bucket()

    buckets: list[ForecastBucketResult] = []
    cumulative = current_load_kg
    for ts in bucket_starts:
        known = known_by_bucket[ts]
        cumulative += known + unknown_per_bucket
        buckets.append(
            ForecastBucketResult(
                timestamp=ts,
                known_inbound_kg=known,
                predicted_unknown_kg=unknown_per_bucket,
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

    # Confidence thô: tăng dần theo số quan sát thật đã tích lũy, cap ở 0.85; đây là placeholder
    # tuyến tính, KHÔNG phải confidence interval thống kê (khác Phase 2 notebook, nơi có
    # residual quantile thật từ validation set) — xem README.
    confidence = min(0.35 + 0.05 * store.observation_count(), 0.85)

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
    )
