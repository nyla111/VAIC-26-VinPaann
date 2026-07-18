from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROUTE_NAMES = {
    "A_DIRECT_ROAD": "di_thang_hcm",
    "B_ROAD_VIA_CT": "qua_can_tho_duong_bo",
    "C_WATER_ROAD_VIA_CT": "qua_can_tho_sa_lan_duong_bo",
    "D_WATER_VIA_CT": "qua_can_tho_duong_thuy",
    "E_ROAD_WATER_VIA_CT": "qua_can_tho_duong_bo_sa_lan",
}


@dataclass(frozen=True)
class RouteCandidate:
    route_code: str
    ten: str
    leg_ids: list[str]
    distance_km: float
    duration_hr_base: float


def _leg_for(legs: dict[str, dict[str, Any]], from_node_id: str, to_node_id: str, mode: str) -> dict[str, Any]:
    matches = [
        leg
        for leg in legs.values()
        if leg["from_node_id"] == from_node_id
        and leg["to_node_id"] == to_node_id
        and leg["mode"] == mode
        and leg["active"]
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one active leg for {from_node_id}->{to_node_id} {mode}, got {len(matches)}")
    return matches[0]


def build_candidates(hub_id: str, legs: dict[str, dict[str, Any]]) -> list[RouteCandidate]:
    hcm = "HCM_MARKET"
    ct = "CT_HUB"
    route_legs = {
        "A_DIRECT_ROAD": [_leg_for(legs, hub_id, hcm, "road")],
        "B_ROAD_VIA_CT": [_leg_for(legs, hub_id, ct, "road"), _leg_for(legs, ct, hcm, "road")],
        "C_WATER_ROAD_VIA_CT": [_leg_for(legs, hub_id, ct, "water"), _leg_for(legs, ct, hcm, "road")],
        "D_WATER_VIA_CT": [_leg_for(legs, hub_id, ct, "water"), _leg_for(legs, ct, hcm, "water")],
        "E_ROAD_WATER_VIA_CT": [_leg_for(legs, hub_id, ct, "road"), _leg_for(legs, ct, hcm, "water")],
    }
    return [
        RouteCandidate(
            route_code=code,
            ten=ROUTE_NAMES[code],
            leg_ids=[leg["leg_id"] for leg in route],
            distance_km=sum(leg["distance_km"] for leg in route),
            duration_hr_base=sum(leg["duration_hr_base"] for leg in route),
        )
        for code, route in route_legs.items()
    ]
