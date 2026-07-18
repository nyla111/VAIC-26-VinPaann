"""In-memory state cho AI2 (v1). Không dùng SQLite — MVP ưu tiên ra output nhanh; xem README
mục "Storage" / roadmap cho việc chuyển sang Backend-as-source-of-truth."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .data_loader import get_fleet_bootstrap_rows
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
        """Mốc tính urgency: harvested_at nếu có (chất lượng nông sản không reset khi đến Cần
        Thơ, đúng đề xuất AI2-plan.pdf mục "Với Data Lead"), else created_at."""
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
    """Đơn giản, single-process, thread-safe bằng 1 lock chung — đủ cho demo hackathon."""

    def __init__(self, data_dir=None) -> None:
        self._lock = threading.RLock()
        self.shipments: dict[str, Shipment] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self.seen_event_ids: dict[str, int] = {}
        self.state_version: int = 0
        self.decision_counter: int = 0
        self.proposal_counter: int = 0
        self.arrival_history: list[ArrivalObservation] = []
        self.manual_weather_override: Optional[dict] = None
        self._bootstrap_fleet(data_dir)

    def _bootstrap_fleet(self, data_dir) -> None:
        for row in get_fleet_bootstrap_rows(data_dir) if data_dir else get_fleet_bootstrap_rows():
            vehicle_id = row["vehicle_id"]
            self.vehicles[vehicle_id] = Vehicle(
                vehicle_id=vehicle_id,
                mode=Mode(row["mode"]),
                capacity_kg=float(row["capacity_ton"]) * 1000.0,
                status=VehicleStatus(row["status"]),
                available_from=row["_available_dt"],
                supports_refrigeration=bool(row["has_reefer"]),
                location="can_tho",
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
            self.shipments[shipment.shipment_id] = shipment

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        return self.shipments.get(shipment_id)

    def mark_arrived(self, shipment_id: str, actual_arrival_at: datetime, actual_weight_kg: float) -> None:
        with self._lock:
            shipment = self.shipments[shipment_id]
            shipment.state = ShipmentState.ARRIVED_WAITING
            shipment.actual_arrival_at = actual_arrival_at
            shipment.actual_weight_kg = actual_weight_kg
            bucket = actual_arrival_at.replace(
                minute=(actual_arrival_at.minute // 30) * 30, second=0, microsecond=0
            )
            self.arrival_history.append(ArrivalObservation(bucket_start=bucket, weight_kg=actual_weight_kg))

    def cancel_shipment(self, shipment_id: str) -> None:
        with self._lock:
            self.shipments[shipment_id].state = ShipmentState.CANCELLED

    def pending_shipments(self, outbound_mode: Optional[Mode] = None) -> list[Shipment]:
        result = [
            s for s in self.shipments.values()
            if s.state == ShipmentState.ARRIVED_WAITING
        ]
        if outbound_mode is not None:
            result = [s for s in result if s.outbound_mode_from_can_tho == outbound_mode]
        return result

    def in_transit_shipments(self, outbound_mode: Optional[Mode] = None) -> list[Shipment]:
        result = [
            s for s in self.shipments.values()
            if s.state in (ShipmentState.ROUTED_TO_CAN_THO, ShipmentState.IN_TRANSIT_TO_CAN_THO)
        ]
        if outbound_mode is not None:
            result = [s for s in result if s.outbound_mode_from_can_tho == outbound_mode]
        return result

    # -- vehicles ------------------------------------------------------
    def upsert_vehicle(self, vehicle: Vehicle) -> None:
        with self._lock:
            self.vehicles[vehicle.vehicle_id] = vehicle

    def available_vehicles(self, mode: Mode, decision_ts: datetime, needs_reefer: bool = False) -> list[Vehicle]:
        return [
            v for v in self.vehicles.values()
            if v.mode == mode
            and v.status == VehicleStatus.AVAILABLE
            and v.available_from <= decision_ts
            and (v.supports_refrigeration or not needs_reefer)
        ]

    # -- rolling mean forecast input --------------------------------------
    def rolling_mean_kg_per_bucket(self, lookback: int = 20, bucket_minutes: int = 30) -> float:
        """Trung bình weight/bucket quan sát được từ event thật, dùng làm forecast baseline
        cho 'predicted_unknown_kg'. 0.0 nếu chưa có lịch sử (demo mới khởi động).

        Chia cho *toàn bộ* số bucket đã trôi qua kể từ quan sát đầu tiên trong lookback window
        (kể cả bucket không có hàng đến), không chỉ chia cho số bucket có dữ liệu — nếu không sẽ
        overestimate khi arrival thưa (VD 1 shipment 4 tấn trong 1 bucket sẽ bị hiểu nhầm là
        "4 tấn/bucket" thay vì trung bình loãng ra theo thời gian). Với rất ít lịch sử (1-2
        event), số này vẫn nhiễu — xem README mục forecast v1 / confidence."""

        if not self.arrival_history:
            return 0.0
        recent = self.arrival_history[-lookback:]
        total_weight = sum(obs.weight_kg for obs in recent)
        span_start = min(obs.bucket_start for obs in recent)
        span_end = max(obs.bucket_start for obs in recent)
        n_buckets = int((span_end - span_start).total_seconds() / (bucket_minutes * 60)) + 1
        return total_weight / max(n_buckets, 1)

    def observation_count(self) -> int:
        return len(self.arrival_history)
