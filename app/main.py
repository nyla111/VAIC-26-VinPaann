"""FastAPI app cho AI Layer 2 - Forecast + Dispatch Agent.

Chạy:
    uvicorn ai2_dispatch.app.main:app --reload --host 127.0.0.1 --port 8001

Swagger UI: http://127.0.0.1:8001/docs
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import decision_engine
from .agent import periodic_tick_loop
from .data_loader import DEFAULT_DATA_DIR
from .enums import Mode, ROUTES_REQUIRING_AI2, ShipmentState
from .schemas import (
    CurrentState,
    DispatchCompletedEvent,
    DispatchOrderProposal,
    DispatchStatusResponse,
    ErrorDetail,
    ErrorResponse,
    EventResponse,
    ForecastBucket,
    ForecastConfig,
    ForecastResponse,
    ForecastSummary,
    PredictedFullLoad,
    PriorityScoreBreakdown,
    SelectedVehicle,
    ShipmentArrivedEvent,
    ShipmentCancelledEvent,
    ShipmentRoutedEvent,
    VehicleStatusEvent,
    WeatherUpdateEvent,
)
from .state_store import Shipment, StateStore, Vehicle

# AI2_STATE_FILE cho phép override đường dẫn persist (tests dùng tmp_path riêng để không đụng
# state thật / không bị leftover giữa các lần chạy test — xem tests/test_smoke.py).
_DEFAULT_STATE_FILE = Path(__file__).resolve().parents[1] / ".state" / "ai2_state.pkl"
STATE_FILE = Path(os.environ.get("AI2_STATE_FILE", str(_DEFAULT_STATE_FILE)))

store = StateStore(data_dir=DEFAULT_DATA_DIR, persist_path=STATE_FILE)
DEFAULT_CONFIG = decision_engine.DecisionConfig()

# AI2_DISABLE_AGENT_TICK=1 tắt vòng lặp agentic
_AGENT_TICK_ENABLED = os.environ.get("AI2_DISABLE_AGENT_TICK") != "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if _AGENT_TICK_ENABLED:
        task = asyncio.create_task(periodic_tick_loop(store, DEFAULT_CONFIG))
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="AI Layer 2 - Forecast + Dispatch Agent", version="0.1.0", lifespan=lifespan)


def _error(status_code: int, code: str, message: str, details: Optional[dict] = None):
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorDetail(code=code, message=message, details=details)).model_dump(
            mode="json"
        ),
    )


def _default_outbound_mode() -> Mode:
    road_weight = sum(s.effective_weight_kg for s in store.pending_shipments(Mode.ROAD))
    water_weight = sum(s.effective_weight_kg for s in store.pending_shipments(Mode.WATER))
    return Mode.WATER if water_weight > road_weight else Mode.ROAD


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "state_version": store.state_version, "shipments": len(store.shipments)}


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/events/shipment-routed", response_model=EventResponse)
def shipment_routed(event: ShipmentRoutedEvent):
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )

    payload = event.shipment
    if payload.selected_route not in ROUTES_REQUIRING_AI2:
        return _error(
            422,
            "ROUTE_NOT_APPLICABLE",
            f"Route {payload.selected_route.value} không đi qua Cần Thơ, không thuộc phạm vi AI2.",
            {"selected_route": payload.selected_route.value},
        )
    store.add_shipment(
        Shipment(
            shipment_id=payload.shipment_id,
            hub_id=payload.hub_id,
            commodity_id=payload.commodity_id,
            weight_kg=payload.weight_kg,
            selected_route=payload.selected_route,
            inbound_mode_to_can_tho=payload.inbound_mode_to_can_tho,
            outbound_mode_from_can_tho=payload.outbound_mode_from_can_tho,
            created_at=payload.created_at,
            harvested_at=payload.harvested_at,
            eta_can_tho=payload.eta_can_tho,
            state=ShipmentState.ROUTED_TO_CAN_THO,
        )
    )
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@app.post("/api/v1/events/shipment-arrived", response_model=EventResponse)
def shipment_arrived(event: ShipmentArrivedEvent):
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    shipment = store.get_shipment(event.shipment_id)
    if shipment is None:
        return _error(404, "SHIPMENT_NOT_FOUND", f"Shipment {event.shipment_id} was not found.")
    if shipment.state == ShipmentState.DISPATCHED:
        return _error(
            409,
            "INVALID_STATE_TRANSITION",
            "A dispatched shipment cannot return to arrived_waiting.",
        )
    store.mark_arrived(event.shipment_id, event.actual_arrival_at, event.actual_weight_kg)
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@app.post("/api/v1/events/shipment-cancelled", response_model=EventResponse)
def shipment_cancelled(event: ShipmentCancelledEvent):
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    shipment = store.get_shipment(event.shipment_id)
    if shipment is None:
        return _error(404, "SHIPMENT_NOT_FOUND", f"Shipment {event.shipment_id} was not found.")
    store.cancel_shipment(event.shipment_id)
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@app.post("/api/v1/events/vehicle-status", response_model=EventResponse)
def vehicle_status(event: VehicleStatusEvent):
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    v = event.vehicle
    store.upsert_vehicle(
        Vehicle(
            vehicle_id=v.vehicle_id,
            mode=v.mode,
            capacity_kg=v.capacity_kg,
            status=v.status,
            available_from=v.available_from,
            supports_refrigeration=v.supports_refrigeration,
            location=v.location,
        )
    )
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@app.post("/api/v1/events/weather-update", response_model=EventResponse)
def weather_update(event: WeatherUpdateEvent):

    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    store.manual_weather_override = {
        "road_blocked": event.road_blocked,
        "water_blocked": event.water_blocked,
        "road_risk": event.road_risk,
        "water_risk": event.water_risk,
        "valid_from": event.valid_from,
        "valid_until": event.valid_until,
    }
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@app.post("/api/v1/events/dispatch-completed", response_model=EventResponse)
def dispatch_completed(event: DispatchCompletedEvent):
    """Backend gọi sau khi đã xác nhận dispatch order (dựa trên `dispatch_order_proposal` mà
    `GET /api/v1/dispatch-status` trả về). Không có event này, shipment đã dispatch sẽ tiếp
    tục bị tính vào pending pool."""

    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    missing = [sid for sid in event.shipment_ids if store.get_shipment(sid) is None]
    if missing:
        return _error(404, "SHIPMENT_NOT_FOUND", f"Shipment(s) not found: {missing}", {"shipment_ids": missing})
    store.mark_dispatched(event.shipment_ids, event.vehicle_id, event.actual_departure_at)
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


# ---------------------------------------------------------------------------
# Forecast + dispatch status
# ---------------------------------------------------------------------------

@app.get("/api/v1/forecast", response_model=ForecastResponse)
def get_forecast(
    outbound_mode: Optional[Mode] = Query(default=None),
    decision_ts: Optional[datetime] = Query(default=None),
):
    mode = outbound_mode or _default_outbound_mode()
    ts = decision_ts or datetime.now(timezone.utc)
    result = decision_engine.evaluate(store, ts, mode, DEFAULT_CONFIG)
    forecast = result.forecast

    return ForecastResponse(
        forecast_id=f"forecast_{store.state_version:03d}",
        generated_at=forecast.generated_at,
        config=ForecastConfig(
            bucket_minutes=forecast.bucket_minutes,
            horizon_hours=forecast.horizon_hours,
            model_name=forecast.model_name,
        ),
        current_load_kg=forecast.current_load_kg,
        predicted_full_load=PredictedFullLoad(
            vehicle_id=forecast.target_vehicle.vehicle_id if forecast.target_vehicle else None,
            vehicle_capacity_kg=forecast.target_vehicle.capacity_kg if forecast.target_vehicle else None,
            predicted_full_load_time=forecast.predicted_full_load_time,
            predicted_load_kg=forecast.predicted_load_kg,
            confidence=forecast.confidence,
        ),
        buckets=[
            ForecastBucket(
                timestamp=b.timestamp,
                known_inbound_kg=b.known_inbound_kg,
                predicted_unknown_kg=b.predicted_unknown_kg,
                predicted_cumulative_load_kg=b.predicted_cumulative_load_kg,
            )
            for b in forecast.buckets
        ],
    )


@app.get("/api/v1/dispatch-status", response_model=DispatchStatusResponse)
def get_dispatch_status(
    outbound_mode: Optional[Mode] = Query(default=None),
    decision_ts: Optional[datetime] = Query(default=None),
):
    mode = outbound_mode or _default_outbound_mode()
    ts = decision_ts or datetime.now(timezone.utc)
    result = decision_engine.evaluate(store, ts, mode, DEFAULT_CONFIG)

    decision_id = store.next_decision_id()

    dispatch_order_proposal = None
    if result.decision.value == "dispatch_now" and result.selected_vehicle is not None:
        pending = store.pending_shipments(mode)
        dispatch_order_proposal = DispatchOrderProposal(
            proposal_id=store.next_proposal_id(),
            vehicle_id=result.selected_vehicle.vehicle_id,
            shipment_ids=[s.shipment_id for s in pending],
            total_weight_kg=result.current_load_kg,
            capacity_kg=result.selected_vehicle.capacity_kg,
            fill_ratio=result.fill_ratio,
            outbound_mode=mode,
            destination="ho_chi_minh",
            proposed_departure_time=result.proposed_departure_time or ts,
        )

    return DispatchStatusResponse(
        decision_id=decision_id,
        generated_at=ts,
        state_version=store.state_version,
        decision=result.decision,
        reason_codes=result.reason_codes,
        explanation=result.explanation,
        selected_vehicle=(
            SelectedVehicle(
                vehicle_id=result.selected_vehicle.vehicle_id,
                mode=result.selected_vehicle.mode,
                capacity_kg=result.selected_vehicle.capacity_kg,
            )
            if result.selected_vehicle
            else None
        ),
        current_state=CurrentState(
            current_load_kg=result.current_load_kg,
            fill_ratio=result.fill_ratio,
            waiting_shipment_count=result.waiting_shipment_count,
        ),
        priority_score=(
            PriorityScoreBreakdown(
                fill_component=result.priority_score.fill_component,
                urgency_component=result.priority_score.urgency_component,
                weather_component=result.priority_score.weather_component,
                weights={
                    "fill": DEFAULT_CONFIG.alpha_fill,
                    "urgency": DEFAULT_CONFIG.beta_urgency,
                    "weather": DEFAULT_CONFIG.gamma_weather,
                },
                total_score=result.priority_score.total_score,
                dispatch_threshold=DEFAULT_CONFIG.dispatch_threshold,
            )
            if result.priority_score
            else None
        ),
        forecast_summary=ForecastSummary(
            predicted_full_load_time=result.forecast.predicted_full_load_time,
            forecast_confidence=result.forecast.confidence,
        ),
        proposed_departure_time=result.proposed_departure_time,
        dispatch_order_proposal=dispatch_order_proposal,
    )
