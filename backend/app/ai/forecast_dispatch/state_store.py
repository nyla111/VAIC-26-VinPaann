"""SQLite-backed StateStore for AI Layer 2.
Replaces the temporary in-memory state with dynamic database queries to ensure persistence.
Breaks circular imports by importing the database engine locally inside session scopes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select
from app.models import Order as DBOrder, Vehicle as DBVehicle
from .enums import Mode, RouteEnum, ShipmentState, VehicleStatus


@dataclass
class Shipment:
    shipment_id: str
    hub_id: str
    commodity_id: str
    weight_kg: float
    selected_route: RouteEnum
    inbound_mode_to_can_tho: Optional[Mode]
    outbound_mode_from_can_tho: Mode
    created_at: datetime
    harvested_at: Optional[datetime]
    eta_can_tho: datetime
    state: ShipmentState = ShipmentState.ROUTED_TO_CAN_THO
    actual_arrival_at: Optional[datetime] = None
    actual_weight_kg: Optional[float] = None

    @property
    def urgency_reference_ts(self) -> datetime:
        return self.harvested_at or self.created_at

    @property
    def effective_weight_kg(self) -> float:
        return self.actual_weight_kg if self.actual_weight_kg is not None else self.weight_kg


@dataclass
class Vehicle:
    vehicle_id: str
    mode: Mode
    capacity_kg: float
    status: VehicleStatus
    available_from: datetime
    supports_refrigeration: bool = False
    location: str = "can_tho"


@dataclass
class ArrivalObservation:
    bucket_start: datetime
    weight_kg: float


class StateStore:
    """
    Database-backed StateStore for Layer 2.
    Translates all in-memory collections into real-time SQLite SQLModel queries.
    """

    def __init__(self, data_dir=None) -> None:
        self._lock = threading.RLock()
        self.seen_event_ids: dict[str, int] = {}
        self.state_version: int = 0
        self.decision_counter: int = 0
        self.proposal_counter: int = 0
        self.manual_weather_override: Optional[dict] = None
        # Bootstrapping is managed at database initialization startup

    def _to_shipment_obj(self, db_order: DBOrder) -> Shipment:
        created_dt = datetime.fromisoformat(db_order.timestamp) if db_order.timestamp else datetime.now(timezone.utc)
        
        # Handle timezones safely
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)

        from .enums import AI1_ROUTE_TO_AI2_ROUTE
        route_info = AI1_ROUTE_TO_AI2_ROUTE.get(
            db_order.selected_route_id, 
            (RouteEnum.B_ROAD_VIA_CT, Mode.ROAD, Mode.ROAD)
        )
        
        actual_arr = None
        if db_order.actual_arrival_at:
            actual_arr = datetime.fromisoformat(db_order.actual_arrival_at)
            if actual_arr.tzinfo is None:
                actual_arr = actual_arr.replace(tzinfo=timezone.utc)

        harvested_dt = None
        if db_order.harvested_at:
            harvested_dt = datetime.fromisoformat(db_order.harvested_at)
            if harvested_dt.tzinfo is None:
                harvested_dt = harvested_dt.replace(tzinfo=timezone.utc)

        return Shipment(
            shipment_id=str(db_order.id),
            hub_id=db_order.hub_id,
            commodity_id=db_order.commodity_id or "",
            weight_kg=db_order.khoi_luong_kg,
            selected_route=route_info[0],
            inbound_mode_to_can_tho=route_info[1],
            outbound_mode_from_can_tho=route_info[2],
            created_at=created_dt,
            harvested_at=harvested_dt,
            eta_can_tho=actual_arr if actual_arr else created_dt,
            state=ShipmentState(db_order.state),
            actual_arrival_at=actual_arr,
            actual_weight_kg=db_order.actual_weight_kg
        )

    # -- idempotency -----------------------------------------------------
    def is_duplicate_event(self, event_id: str) -> bool:
        return event_id in self.seen_event_ids

    def mark_event_seen(self, event_id: str) -> int:
        with self._lock:
            self.state_version += 1
            self.seen_event_ids[event_id] = self.state_version
            return self.state_version

    def next_decision_id(self) -> str:
        with self._lock:
            self.decision_counter += 1
            return f"decision_{self.decision_counter:03d}"

    def next_proposal_id(self) -> str:
        with self._lock:
            self.proposal_counter += 1
            return f"proposal_{self.proposal_counter:03d}"

    # -- shipments ---------------------------------------------------------
    def add_shipment(self, shipment: Shipment) -> None:
        with self._lock:
            from app.database import engine
            with Session(engine) as session:
                order_id = int(shipment.shipment_id) if shipment.shipment_id.isdigit() else None
                db_order = session.get(DBOrder, order_id) if order_id else None
                if db_order:
                    db_order.selected_route_id = shipment.selected_route.value
                    db_order.state = shipment.state.value
                    session.add(db_order)
                else:
                    db_order = DBOrder(
                        hub_id=shipment.hub_id,
                        commodity_id=shipment.commodity_id,
                        loai_hang="",
                        khoi_luong_kg=shipment.weight_kg,
                        timestamp=shipment.created_at.isoformat(),
                        created_at=datetime.now(timezone.utc).isoformat(),
                        selected_route_id=shipment.selected_route.value,
                        state=shipment.state.value
                    )
                    session.add(db_order)
                session.commit()

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        from app.database import engine
        with Session(engine) as session:
            order_id = int(shipment_id) if shipment_id.isdigit() else None
            if not order_id:
                return None
            db_order = session.get(DBOrder, order_id)
            return self._to_shipment_obj(db_order) if db_order else None

    def mark_arrived(self, shipment_id: str, actual_arrival_at: datetime, actual_weight_kg: float) -> None:
        with self._lock:
            from app.database import engine
            with Session(engine) as session:
                order_id = int(shipment_id) if shipment_id.isdigit() else None
                if order_id:
                    db_order = session.get(DBOrder, order_id)
                    if db_order:
                        db_order.state = "arrived_waiting"
                        db_order.actual_arrival_at = actual_arrival_at.isoformat()
                        db_order.actual_weight_kg = actual_weight_kg
                        session.add(db_order)
                        session.commit()

    def cancel_shipment(self, shipment_id: str) -> None:
        with self._lock:
            from app.database import engine
            with Session(engine) as session:
                order_id = int(shipment_id) if shipment_id.isdigit() else None
                if order_id:
                    db_order = session.get(DBOrder, order_id)
                    if db_order:
                        db_order.state = "cancelled"
                        session.add(db_order)
                        session.commit()

    def pending_shipments(self, outbound_mode: Optional[Mode] = None) -> list[Shipment]:
        from app.database import engine
        with Session(engine) as session:
            orders = session.exec(select(DBOrder).where(DBOrder.state == "arrived_waiting")).all()
            result = []
            for order in orders:
                ship = self._to_shipment_obj(order)
                if outbound_mode is None or ship.outbound_mode_from_can_tho == outbound_mode:
                    result.append(ship)
            return result

    def in_transit_shipments(self, outbound_mode: Optional[Mode] = None) -> list[Shipment]:
        from app.database import engine
        with Session(engine) as session:
            orders = session.exec(select(DBOrder).where(DBOrder.state.in_(["routed_to_can_tho", "in_transit_to_can_tho"]))).all()
            result = []
            for order in orders:
                ship = self._to_shipment_obj(order)
                if outbound_mode is None or ship.outbound_mode_from_can_tho == outbound_mode:
                    result.append(ship)
            return result

    # -- vehicles ------------------------------------------------------
    def upsert_vehicle(self, vehicle: Vehicle) -> None:
        with self._lock:
            from app.database import engine
            with Session(engine) as session:
                db_veh = session.get(DBVehicle, vehicle.vehicle_id)
                if not db_veh:
                    db_veh = DBVehicle(license_plate=vehicle.vehicle_id)
                db_veh.mode = vehicle.mode.value
                db_veh.capacity_kg = vehicle.capacity_kg
                db_veh.status = vehicle.status.value
                db_veh.available_from = vehicle.available_from.isoformat() if isinstance(vehicle.available_from, datetime) else str(vehicle.available_from)
                db_veh.supports_refrigeration = vehicle.supports_refrigeration
                db_veh.location = vehicle.location
                session.add(db_veh)
                session.commit()

    def available_vehicles(self, mode: Mode, decision_ts: datetime, needs_reefer: bool = False) -> list[Vehicle]:
        from app.database import engine
        with Session(engine) as session:
            vehicles = session.exec(select(DBVehicle).where(
                DBVehicle.mode == mode.value,
                DBVehicle.status == "available",
                DBVehicle.location == "can_tho"
            )).all()
            result = []
            for v in vehicles:
                avail_dt = datetime.fromisoformat(v.available_from) if v.available_from else datetime.min
                
                # Normalize timezone matching
                if decision_ts.tzinfo and not avail_dt.tzinfo:
                    avail_dt = avail_dt.replace(tzinfo=decision_ts.tzinfo)
                elif not decision_ts.tzinfo and avail_dt.tzinfo:
                    avail_dt = avail_dt.replace(tzinfo=None)

                if avail_dt <= decision_ts:
                    if v.supports_refrigeration or not needs_reefer:
                        result.append(Vehicle(
                            vehicle_id=v.license_plate,
                            mode=Mode(v.mode),
                            capacity_kg=v.capacity_kg,
                            status=VehicleStatus(v.status),
                            available_from=avail_dt,
                            supports_refrigeration=v.supports_refrigeration,
                            location=v.location
                        ))
            return result

    # -- rolling mean forecast input --------------------------------------
    @property
    def arrival_history(self) -> list[ArrivalObservation]:
        from app.database import engine
        with Session(engine) as session:
            orders = session.exec(select(DBOrder).where(DBOrder.actual_arrival_at != None)).all()
            history = []
            for o in orders:
                actual_arr = datetime.fromisoformat(o.actual_arrival_at)
                if actual_arr.tzinfo is None:
                    actual_arr = actual_arr.replace(tzinfo=timezone.utc)
                bucket = actual_arr.replace(
                    minute=(actual_arr.minute // 30) * 30, second=0, microsecond=0
                )
                history.append(ArrivalObservation(bucket_start=bucket, weight_kg=o.actual_weight_kg or o.khoi_luong_kg))
            # Sort chronologically
            history.sort(key=lambda x: x.bucket_start)
            return history

    def rolling_mean_kg_per_bucket(self, lookback: int = 20, bucket_minutes: int = 30) -> float:
        history = self.arrival_history
        if not history:
            return 0.0
        recent = history[-lookback:]
        total_weight = sum(obs.weight_kg for obs in recent)
        span_start = min(obs.bucket_start for obs in recent)
        span_end = max(obs.bucket_start for obs in recent)
        n_buckets = int((span_end - span_start).total_seconds() / (bucket_minutes * 60)) + 1
        return total_weight / max(n_buckets, 1)

    def observation_count(self) -> int:
        return len(self.arrival_history)
