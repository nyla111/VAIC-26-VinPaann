"""Enums và bảng map dùng chung cho AI Layer 2.

Route enum ở đây dùng đúng 5 tên trong AI2-plan.pdf (draft contract của Thảo Nhi), vì đó là
enum sẽ lộ ra ngoài API cho Backend/Frontend. AI1 thật (route_optimizer/) hiện trả route code
dạng A_DIRECT_ROAD..E_ROAD_WATER_VIA_CT (xem INTEGRATION_LOP_AI_1.md); AI1_ROUTE_TO_AI2_ROUTE
là bảng map giữa hai hệ enum đó, để Backend chỉ cần forward nguyên route_code của AI1 nếu muốn,
AI2 tự dịch.
"""

from __future__ import annotations

from enum import Enum


class RouteEnum(str, Enum):
    DIRECT_HCM_ROAD = "direct_hcm_road"
    VIA_CAN_THO_ROAD_THEN_ROAD = "via_can_tho_road_then_road"
    VIA_CAN_THO_WATER_THEN_ROAD = "via_can_tho_water_then_road"
    VIA_CAN_THO_WATER_THEN_WATER = "via_can_tho_water_then_water"
    VIA_CAN_THO_ROAD_THEN_WATER = "via_can_tho_road_then_water"


class Mode(str, Enum):
    ROAD = "road"
    WATER = "water"


# route_code AI1 thật (A-E, xem route_optimizer/candidates.py) -> (RouteEnum, inbound_mode, outbound_mode)
# inbound_mode = None nghĩa là route không đi qua Cần Thơ.
AI1_ROUTE_TO_AI2_ROUTE: dict[str, tuple[RouteEnum, Mode | None, Mode]] = {
    "A_DIRECT_ROAD": (RouteEnum.DIRECT_HCM_ROAD, None, Mode.ROAD),
    "B_ROAD_VIA_CT": (RouteEnum.VIA_CAN_THO_ROAD_THEN_ROAD, Mode.ROAD, Mode.ROAD),
    "C_WATER_ROAD_VIA_CT": (RouteEnum.VIA_CAN_THO_WATER_THEN_ROAD, Mode.WATER, Mode.ROAD),
    "D_WATER_VIA_CT": (RouteEnum.VIA_CAN_THO_WATER_THEN_WATER, Mode.WATER, Mode.WATER),
    "E_ROAD_WATER_VIA_CT": (RouteEnum.VIA_CAN_THO_ROAD_THEN_WATER, Mode.ROAD, Mode.WATER),
}

# Route nào cần AI2 xử lý (loại trừ direct_hcm_road, theo phạm vi trách nhiệm AI2-plan.pdf mục 2).
ROUTES_REQUIRING_AI2 = {
    RouteEnum.VIA_CAN_THO_ROAD_THEN_ROAD,
    RouteEnum.VIA_CAN_THO_WATER_THEN_ROAD,
    RouteEnum.VIA_CAN_THO_WATER_THEN_WATER,
    RouteEnum.VIA_CAN_THO_ROAD_THEN_WATER,
}

ROUTE_EXPECTED_MODES: dict[RouteEnum, tuple[Mode | None, Mode]] = {
    route: (inbound, outbound) for route, inbound, outbound in AI1_ROUTE_TO_AI2_ROUTE.values()
}


class ShipmentState(str, Enum):
    ROUTED_TO_CAN_THO = "routed_to_can_tho"
    IN_TRANSIT_TO_CAN_THO = "in_transit_to_can_tho"
    ARRIVED_WAITING = "arrived_waiting"
    ASSIGNED_TO_VEHICLE = "assigned_to_vehicle"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Vehicle status dùng đúng 4 giá trị canonical fleet.status (SCHEMA.md mục 6), KHÔNG dùng 6
# giá trị trong AI2-plan.pdf (available/loading/dispatched/in_transit/maintenance/unavailable).
# Deviation có chủ đích: xem ai2_dispatch/README.md mục "Điểm khác với AI2-plan.pdf".
class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


class Decision(str, Enum):
    DISPATCH_NOW = "dispatch_now"
    WAIT_FOR_LOAD = "wait_for_load"
    WAIT_FOR_VEHICLE = "wait_for_vehicle"


class ReasonCode(str, Enum):
    VEHICLE_FULL = "vehicle_full"
    PRIORITY_SCORE_REACHED = "priority_score_reached"
    SAFE_WAIT_LIMIT_REACHED = "safe_wait_limit_reached"
    HIGH_URGENCY = "high_urgency"
    WEATHER_RISK_INCREASING = "weather_risk_increasing"
    WEATHER_BLOCKED = "weather_blocked"
    VEHICLE_UNAVAILABLE = "vehicle_unavailable"
    VEHICLE_INCOMPATIBLE = "vehicle_incompatible"
    SCORE_BELOW_THRESHOLD = "score_below_threshold"
    FULL_LOAD_EXPECTED_SOON = "full_load_expected_soon"
    INSUFFICIENT_FORECAST_CONFIDENCE = "insufficient_forecast_confidence"
    NO_PENDING_SHIPMENTS = "no_pending_shipments"
