from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.ai.forecast_dispatch import decision_engine
from app.ai.forecast_dispatch.data_loader import DEFAULT_DATA_DIR
from app.ai.forecast_dispatch.enums import Mode, ShipmentState
from app.ai.forecast_dispatch.state_store import StateStore, Vehicle, Shipment
from app.ai.forecast_dispatch.schemas import (
    ForecastResponse,
    DispatchStatusResponse,
    VehicleStatusEvent,
    WeatherUpdateEvent,
    EventResponse,
    PredictedFullLoad,
    ForecastConfig,
    ForecastBucket,
    DispatchOrderProposal,
    SelectedVehicle,
    CurrentState,
    PriorityScoreBreakdown,
    ForecastSummary,
    ErrorResponse,
    ErrorDetail
)

router = APIRouter()
store = StateStore(data_dir=DEFAULT_DATA_DIR)
DEFAULT_CONFIG = decision_engine.DecisionConfig()


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


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast(
    outbound_mode: Optional[Mode] = Query(default=None),
    decision_ts: Optional[datetime] = Query(default=None),
):
    """
    Retrieves Layer 2 accumulation forecast for the selected outbound transport mode.
    """
    mode = outbound_mode or _default_outbound_mode()
    ts = decision_ts or datetime.now(timezone.utc)
    
    # Ensure timezone awareness
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    result = decision_engine.evaluate(store, ts, mode, DEFAULT_CONFIG)
    forecast = result.forecast

    return ForecastResponse(
        forecast_id=f"forecast_{store.state_version:03d}",
        generated_at=forecast.generated_at,
        config=ForecastConfig(bucket_minutes=forecast.bucket_minutes, horizon_hours=forecast.horizon_hours),
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


@router.get("/dispatch-status", response_model=DispatchStatusResponse)
def get_dispatch_status(
    outbound_mode: Optional[Mode] = Query(default=None),
    decision_ts: Optional[datetime] = Query(default=None),
):
    """
    Checks the active dispatch status (DISPATCH_NOW / WAIT_FOR_LOAD / WAIT_FOR_VEHICLE) at Can Tho Hub.
    """
    mode = outbound_mode or _default_outbound_mode()
    ts = decision_ts or datetime.now(timezone.utc)
    
    # Ensure timezone awareness
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

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


@router.post("/events/vehicle-status", response_model=EventResponse)
def vehicle_status(event: VehicleStatusEvent):
    """
    Registers or updates a vehicle's operational state at Can Tho Hub.
    """
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
    v = event.vehicle
    
    # Safely format available_from with timezone
    avail_dt = v.available_from
    if avail_dt.tzinfo is None:
        avail_dt = avail_dt.replace(tzinfo=timezone.utc)
        
    store.upsert_vehicle(
        Vehicle(
            vehicle_id=v.vehicle_id,
            mode=v.mode,
            capacity_kg=v.capacity_kg,
            status=v.status,
            available_from=avail_dt,
            supports_refrigeration=v.supports_refrigeration,
            location=v.location,
        )
    )
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)


@router.post("/events/weather-update", response_model=EventResponse)
def weather_update(event: WeatherUpdateEvent):
    """
    Manually overrides outbound weather status (useful for demo and judging scenarios).
    """
    if store.is_duplicate_event(event.event_id):
        return EventResponse(
            accepted=True, event_id=event.event_id, state_version=store.state_version, duplicate=True
        )
        
    valid_from_dt = event.valid_from
    if valid_from_dt.tzinfo is None:
        valid_from_dt = valid_from_dt.replace(tzinfo=timezone.utc)
        
    valid_until_dt = event.valid_until
    if valid_until_dt.tzinfo is None:
        valid_until_dt = valid_until_dt.replace(tzinfo=timezone.utc)

    store.manual_weather_override = {
        "road_blocked": event.road_blocked,
        "water_blocked": event.water_blocked,
        "road_risk": event.road_risk,
        "water_risk": event.water_risk,
        "valid_from": valid_from_dt,
        "valid_until": valid_until_dt,
    }
    version = store.mark_event_seen(event.event_id)
    return EventResponse(accepted=True, event_id=event.event_id, state_version=version, recomputed=True)
