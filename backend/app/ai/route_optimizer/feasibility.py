from __future__ import annotations

from datetime import datetime
from typing import Any

from .data_loader import DataStore, nearest_previous


def leg_weather_factor(store: DataStore, leg: dict[str, Any], decision_ts: datetime) -> tuple[float, str | None, str | None]:
    rows = store.weather_by_node.get(leg["from_node_id"], [])
    weather = nearest_previous(rows, decision_ts)
    if weather is None:
        return 1.0, None, "missing_weather"
    if leg["mode"] == "road":
        return weather["road_factor"], weather["ts"], None
    return weather["water_factor"], weather["ts"], None


def water_bulletin_reason(store: DataStore, node_id: str, decision_ts: datetime) -> str | None:
    for bulletin in store.weather_bulletins:
        if bulletin["node_id"] != node_id:
            continue
        if not (bulletin["_valid_from_dt"] <= decision_ts <= bulletin["_valid_to_dt"]):
            continue
        status = bulletin["water_navigation_status"]
        if status not in {"open", "not_applicable"}:
            return "tuyen_duong_thuy_khong_an_toan"
    return None


def evaluate_route_feasibility(
    store: DataStore,
    leg_ids: list[str],
    commodity: dict[str, Any] | None,
    decision_ts: datetime,
) -> tuple[bool, str | None, float, str | None]:
    total_factor = 0.0
    weather_ts = None
    legs = [store.legs[leg_id] for leg_id in leg_ids]

    if commodity is not None and not commodity["water_ok"] and any(leg["mode"] == "water" for leg in legs):
        return False, "hang_khong_phu_hop_duong_thuy", 0.0, None

    for leg in legs:
        factor, ts, reason = leg_weather_factor(store, leg, decision_ts)
        weather_ts = ts or weather_ts
        if reason:
            return False, reason, 0.0, weather_ts
        if leg["mode"] == "water":
            if factor > 1.0:
                return False, "muc_nuoc_khong_an_toan", 0.0, weather_ts
            bulletin_reason = water_bulletin_reason(store, leg["from_node_id"], decision_ts)
            if bulletin_reason:
                return False, bulletin_reason, 0.0, weather_ts
        total_factor += leg["duration_hr_base"] * factor

    return True, None, total_factor, weather_ts
