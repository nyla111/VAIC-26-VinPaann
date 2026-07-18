"""Hard constraints + additive Priority Score.

Priority Score không được override hard constraint. Thứ tự check:
  1. Không có phương tiện phù hợp           -> wait_for_vehicle
  2. Tuyến (outbound) không an toàn          -> wait_for_load, reason weather_blocked
  3. Có shipment chạm max_safe_wait_hours    -> dispatch_now
  4. Đã đầy tải (fill_ratio >= 1.0)          -> dispatch_now
  5. Còn lại: dùng priority_score vs threshold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .data_loader import (
    DEFAULT_DATA_DIR,
    get_cargo_profile_or_default,
    get_data_store,
    get_outbound_weather_assessment,
)
from .enums import Decision, Mode, ReasonCode
from .forecasting import ForecastResult, build_forecast
from .state_store import Shipment, StateStore, Vehicle


@dataclass(frozen=True)
class DecisionConfig:
    # Tuned 2026-07-18 trên data thật
    alpha_fill: float = 0.60
    beta_urgency: float = 0.30
    gamma_weather: float = 0.10
    dispatch_threshold: float = 0.65
    bucket_minutes: int = 30
    horizon_hours: int = 6
    weights_source: str = "simulation_tuning_2026-07-18 (ai2_dispatch/reports/tuning_report.json)"

    def __post_init__(self) -> None:
        total = self.alpha_fill + self.beta_urgency + self.gamma_weather
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"alpha+beta+gamma phải = 1, hiện tại = {total}")


@dataclass
class PriorityScoreResult:
    fill_component: float
    urgency_component: float
    weather_component: float
    total_score: float


@dataclass
class DecisionResult:
    decision: Decision
    reason_codes: list[ReasonCode]
    explanation: str
    selected_vehicle: Optional[Vehicle]
    current_load_kg: float
    fill_ratio: float
    waiting_shipment_count: int
    priority_score: Optional[PriorityScoreResult]
    forecast: ForecastResult
    proposed_departure_time: Optional[datetime]


def _select_vehicle(
    store: StateStore,
    outbound_mode: Mode,
    decision_ts: datetime,
    needs_reefer: bool,
    total_weight_kg: float,
) -> Optional[Vehicle]:
    candidates = store.available_vehicles(outbound_mode, decision_ts, needs_reefer=needs_reefer)
    if not candidates:
        return None
    sufficient = [v for v in candidates if v.capacity_kg >= total_weight_kg]
    if sufficient:
        return min(sufficient, key=lambda v: v.capacity_kg)
    # Không xe nào đủ tải toàn bộ -> chọn xe lớn nhất hiện có (partial load).
    # Assumption v1: chưa hỗ trợ gán nhiều xe cho 1 lô hàng cùng lúc.
    return max(candidates, key=lambda v: v.capacity_kg)


def evaluate(
    store: StateStore,
    decision_ts: datetime,
    outbound_mode: Mode,
    config: DecisionConfig = DecisionConfig(),
    data_dir=DEFAULT_DATA_DIR,
) -> DecisionResult:
    pending = store.pending_shipments(outbound_mode)
    waiting_shipment_count = len(pending)
    total_weight_kg = sum(s.effective_weight_kg for s in pending)

    cargo_profiles = {
        s.shipment_id: get_cargo_profile_or_default(s.commodity_id, data_dir) for s in pending
    }
    needs_reefer_any = any(p.needs_reefer for p in cargo_profiles.values())

    vehicle = _select_vehicle(store, outbound_mode, decision_ts, needs_reefer_any, total_weight_kg)

    forecast = build_forecast(
        store,
        decision_ts,
        outbound_mode,
        bucket_minutes=config.bucket_minutes,
        horizon_hours=config.horizon_hours,
        target_vehicle=vehicle,
    )

    reason_codes: list[ReasonCode] = []

    # -- pending trống -----------------------------------------------------
    if waiting_shipment_count == 0:
        return DecisionResult(
            decision=Decision.WAIT_FOR_LOAD,
            reason_codes=[ReasonCode.NO_PENDING_SHIPMENTS],
            explanation="Không có shipment nào đang chờ dispatch cho outbound_mode này.",
            selected_vehicle=vehicle,
            current_load_kg=0.0,
            fill_ratio=0.0,
            waiting_shipment_count=0,
            priority_score=None,
            forecast=forecast,
            proposed_departure_time=None,
        )

    # -- hard constraint 1: không có xe phù hợp -----------------------------
    if vehicle is None:
        return DecisionResult(
            decision=Decision.WAIT_FOR_VEHICLE,
            reason_codes=[ReasonCode.VEHICLE_UNAVAILABLE],
            explanation=(
                f"{waiting_shipment_count} shipment đang chờ ({total_weight_kg:.0f} kg) nhưng "
                f"không có phương tiện mode={outbound_mode.value} khả dụng tại Cần Thơ."
            ),
            selected_vehicle=None,
            current_load_kg=total_weight_kg,
            fill_ratio=0.0,
            waiting_shipment_count=waiting_shipment_count,
            priority_score=None,
            forecast=forecast,
            proposed_departure_time=None,
        )

    fill_ratio = min(total_weight_kg / vehicle.capacity_kg, 1.0) if vehicle.capacity_kg else 0.0

    # -- hard constraint 2: tuyến không an toàn -----------------------------
    store_data = get_data_store(data_dir)
    override = store.manual_weather_override
    if override and override["valid_from"] <= decision_ts <= override["valid_until"]:
        weather = override
    else:
        weather = get_outbound_weather_assessment(store_data, decision_ts)
    if isinstance(weather, dict):
        blocked = weather["water_blocked"] if outbound_mode == Mode.WATER else weather["road_blocked"]
        weather_risk = weather["water_risk"] if outbound_mode == Mode.WATER else weather["road_risk"]
    else:
        blocked = weather.water_blocked if outbound_mode == Mode.WATER else weather.road_blocked
        weather_risk = weather.risk

    if blocked:
        return DecisionResult(
            decision=Decision.WAIT_FOR_LOAD,
            reason_codes=[ReasonCode.WEATHER_BLOCKED],
            explanation=(
                f"Tuyến Cần Thơ -> HCM ({outbound_mode.value}) đang bị đóng theo bản tin thời "
                "tiết/thủy văn. Không dispatch cho tới khi tuyến mở lại."
            ),
            selected_vehicle=vehicle,
            current_load_kg=total_weight_kg,
            fill_ratio=round(fill_ratio, 4),
            waiting_shipment_count=waiting_shipment_count,
            priority_score=None,
            forecast=forecast,
            proposed_departure_time=None,
        )

    # -- hard constraint 3: shipment chạm max_safe_wait_hours ---------------
    max_urgency_ratio = 0.0
    breaching_shipment: Optional[Shipment] = None
    for shipment in pending:
        profile = cargo_profiles.get(shipment.shipment_id)
        if profile is None or profile.max_safe_wait_hours <= 0:
            continue
        elapsed_hours = (decision_ts - shipment.urgency_reference_ts).total_seconds() / 3600.0
        ratio = elapsed_hours / profile.max_safe_wait_hours
        if ratio > max_urgency_ratio:
            max_urgency_ratio = ratio
            breaching_shipment = shipment
        if ratio >= 1.0:
            return DecisionResult(
                decision=Decision.DISPATCH_NOW,
                reason_codes=[ReasonCode.SAFE_WAIT_LIMIT_REACHED],
                explanation=(
                    f"Shipment {shipment.shipment_id} đã chạm/vượt max_safe_wait_hours "
                    f"({profile.max_safe_wait_hours:.1f}h). Dispatch ngay dù chưa đầy tải."
                ),
                selected_vehicle=vehicle,
                current_load_kg=total_weight_kg,
                fill_ratio=round(fill_ratio, 4),
                waiting_shipment_count=waiting_shipment_count,
                priority_score=None,
                forecast=forecast,
                proposed_departure_time=decision_ts,
            )

    # -- hard constraint 4: đầy tải -----------------------------------------
    if fill_ratio >= 1.0:
        return DecisionResult(
            decision=Decision.DISPATCH_NOW,
            reason_codes=[ReasonCode.VEHICLE_FULL],
            explanation=f"Tải hiện tại {total_weight_kg:.0f} kg >= sức chứa xe {vehicle.capacity_kg:.0f} kg.",
            selected_vehicle=vehicle,
            current_load_kg=total_weight_kg,
            fill_ratio=1.0,
            waiting_shipment_count=waiting_shipment_count,
            priority_score=None,
            forecast=forecast,
            proposed_departure_time=decision_ts,
        )

    # -- priority score ------------------------------------------------------
    urgency_component = min(max_urgency_ratio, 1.0)
    weather_component = max(0.0, min(weather_risk, 1.0))
    total_score = (
        config.alpha_fill * fill_ratio
        + config.beta_urgency * urgency_component
        + config.gamma_weather * weather_component
    )
    score = PriorityScoreResult(
        fill_component=round(fill_ratio, 4),
        urgency_component=round(urgency_component, 4),
        weather_component=round(weather_component, 4),
        total_score=round(total_score, 4),
    )

    if total_score >= config.dispatch_threshold:
        return DecisionResult(
            decision=Decision.DISPATCH_NOW,
            reason_codes=[ReasonCode.PRIORITY_SCORE_REACHED],
            explanation=(
                f"Priority score {total_score:.2f} >= threshold {config.dispatch_threshold:.2f}. "
                f"Fill {fill_ratio:.0%}, urgency {urgency_component:.2f}, weather {weather_component:.2f}."
            ),
            selected_vehicle=vehicle,
            current_load_kg=total_weight_kg,
            fill_ratio=round(fill_ratio, 4),
            waiting_shipment_count=waiting_shipment_count,
            priority_score=score,
            forecast=forecast,
            proposed_departure_time=decision_ts,
        )

    reason_codes = [ReasonCode.SCORE_BELOW_THRESHOLD]
    if forecast.predicted_full_load_time is not None:
        reason_codes.append(ReasonCode.FULL_LOAD_EXPECTED_SOON)
    if forecast.confidence < 0.5:
        reason_codes.append(ReasonCode.INSUFFICIENT_FORECAST_CONFIDENCE)

    explanation = (
        f"Current load is {fill_ratio:.0%} of vehicle capacity. "
        + (
            f"Forecast predicts full load at {forecast.predicted_full_load_time.isoformat()}. "
            if forecast.predicted_full_load_time
            else "Forecast không dự đoán đủ tải trong horizon hiện tại. "
        )
        + f"Priority score {total_score:.2f} < threshold {config.dispatch_threshold:.2f}."
    )

    return DecisionResult(
        decision=Decision.WAIT_FOR_LOAD,
        reason_codes=reason_codes,
        explanation=explanation,
        selected_vehicle=vehicle,
        current_load_kg=total_weight_kg,
        fill_ratio=round(fill_ratio, 4),
        waiting_shipment_count=waiting_shipment_count,
        priority_score=score,
        forecast=forecast,
        proposed_departure_time=forecast.predicted_full_load_time,
    )
