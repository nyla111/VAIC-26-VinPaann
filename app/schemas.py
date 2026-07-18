"""
Pydantic request/response models cho AI Layer 2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import Decision, Mode, ReasonCode, RouteEnum, ShipmentState, VehicleStatus, normalize_route


# ---------------------------------------------------------------------------
# Event: shipment routed to Can Tho
# ---------------------------------------------------------------------------

class ShipmentRoutedPayload(BaseModel):
    shipment_id: str
    hub_id: str
    hub_name: Optional[str] = None
    commodity_id: str
    weight_kg: float = Field(gt=0)


    selected_route: RouteEnum
    # nếu không gửi, AI2 tự suy ra từ selected_route (xem
    # _resolve_and_check_modes). Nếu gửi, phải khớp — không âm thầm ghi đè giá trị caller cung
    # cấp sai.
    inbound_mode_to_can_tho: Optional[Mode] = None
    outbound_mode_from_can_tho: Optional[Mode] = None

    created_at: datetime
    harvested_at: Optional[datetime] = None
    eta_can_tho: datetime

    @field_validator("selected_route", mode="before")
    @classmethod
    def _normalize_selected_route(cls, value):
        if isinstance(value, str):
            return normalize_route(value)
        return value

    @model_validator(mode="after")
    def _resolve_and_check_modes(self) -> "ShipmentRoutedPayload":
        from .enums import ROUTE_EXPECTED_MODES

        expected_inbound, expected_outbound = ROUTE_EXPECTED_MODES[self.selected_route]

        if self.inbound_mode_to_can_tho is None:
            self.inbound_mode_to_can_tho = expected_inbound
        elif self.inbound_mode_to_can_tho != expected_inbound:
            raise ValueError(
                f"inbound_mode_to_can_tho phải là {expected_inbound} cho route "
                f"{self.selected_route.value}"
            )

        if self.outbound_mode_from_can_tho is None:
            self.outbound_mode_from_can_tho = expected_outbound
        elif self.outbound_mode_from_can_tho != expected_outbound:
            raise ValueError(
                f"outbound_mode_from_can_tho phải là {expected_outbound} cho route "
                f"{self.selected_route.value}"
            )
        return self


class ShipmentRoutedEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["shipment_routed_to_can_tho"] = "shipment_routed_to_can_tho"
    occurred_at: datetime
    shipment: ShipmentRoutedPayload


class ShipmentArrivedEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["shipment_arrived_can_tho"] = "shipment_arrived_can_tho"
    occurred_at: datetime
    shipment_id: str
    actual_arrival_at: datetime
    actual_weight_kg: float = Field(gt=0)


class ShipmentCancelledEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["shipment_cancelled"] = "shipment_cancelled"
    occurred_at: datetime
    shipment_id: str
    reason: str


class VehiclePayload(BaseModel):
    vehicle_id: str
    mode: Mode
    capacity_kg: float = Field(gt=0)
    available_capacity_kg: float = Field(ge=0)
    location: str
    status: VehicleStatus
    available_from: datetime
    supports_refrigeration: bool = False


class VehicleStatusEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["vehicle_status_changed"] = "vehicle_status_changed"
    occurred_at: datetime
    vehicle: VehiclePayload


class WeatherUpdateEvent(BaseModel):
    """Override thủ công cho demo."""

    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["weather_updated"] = "weather_updated"
    occurred_at: datetime
    region: str
    road_risk: float = Field(ge=0, le=1)
    water_risk: float = Field(ge=0, le=1)
    road_blocked: bool
    water_blocked: bool
    valid_from: datetime
    valid_until: datetime


class DispatchCompletedEvent(BaseModel):
    """Backend gọi endpoint này sau khi đã xác
    nhận dispatch order (proposal do AI2 đề xuất qua `dispatch_order_proposal`)."""

    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["dispatch_completed"] = "dispatch_completed"
    occurred_at: datetime
    shipment_ids: list[str]
    vehicle_id: str
    actual_departure_at: datetime


class EventResponse(BaseModel):
    accepted: bool
    event_id: str
    state_version: int
    recomputed: bool = False
    duplicate: bool = False
    latest_decision_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ForecastConfig(BaseModel):
    bucket_minutes: int = 30
    horizon_hours: int = 6
    model_name: str = "rolling_mean_v1"


class ForecastBucket(BaseModel):
    timestamp: datetime
    known_inbound_kg: float
    predicted_unknown_kg: float
    predicted_cumulative_load_kg: float


class PredictedFullLoad(BaseModel):
    vehicle_id: Optional[str] = None
    vehicle_capacity_kg: Optional[float] = None
    predicted_full_load_time: Optional[datetime] = None
    predicted_load_kg: Optional[float] = None
    confidence: float = 0.5


class ForecastResponse(BaseModel):
    forecast_id: str
    generated_at: datetime
    config: ForecastConfig
    current_load_kg: float
    predicted_full_load: PredictedFullLoad
    buckets: list[ForecastBucket]


# ---------------------------------------------------------------------------
# Dispatch decision
# ---------------------------------------------------------------------------

class PriorityScoreBreakdown(BaseModel):
    fill_component: float
    urgency_component: float
    weather_component: float
    weights: dict[str, float]
    total_score: float
    dispatch_threshold: float


class SelectedVehicle(BaseModel):
    vehicle_id: str
    mode: Mode
    capacity_kg: float


class CurrentState(BaseModel):
    current_load_kg: float
    fill_ratio: float
    waiting_shipment_count: int


class ForecastSummary(BaseModel):
    predicted_full_load_time: Optional[datetime] = None
    forecast_confidence: float


class DispatchOrderProposal(BaseModel):
    proposal_id: str
    vehicle_id: str
    shipment_ids: list[str]
    total_weight_kg: float
    capacity_kg: float
    fill_ratio: float
    outbound_mode: Mode
    destination: str = "ho_chi_minh"
    proposed_departure_time: datetime


class DispatchStatusResponse(BaseModel):
    decision_id: str
    generated_at: datetime
    state_version: int
    decision: Decision
    reason_codes: list[ReasonCode]
    explanation: str
    selected_vehicle: Optional[SelectedVehicle] = None
    current_state: CurrentState
    priority_score: Optional[PriorityScoreBreakdown] = None
    forecast_summary: ForecastSummary
    proposed_departure_time: Optional[datetime] = None
    dispatch_order_proposal: Optional[DispatchOrderProposal] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
