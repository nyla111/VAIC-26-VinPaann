"""Đọc data canonical thật cho AI2.

Cố tình tái dùng `route_optimizer.data_loader.load_data()` (AI1) thay vì viết parser CSV
riêng, để AI1 và AI2 luôn đọc đúng cùng một `DataStore` từ cùng một `data_dir` — tránh lệch
data giữa 2 lớp AI như từng xảy ra với dataset simulate riêng của AI2 (xem README mục
"Điểm khác với AI2-plan.pdf / notebook cũ").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.ai.route_optimizer.data_loader import DEFAULT_DATA_DIR, DataStore, load_data

CAN_THO_NODE_ID = "CT_HUB"
HCM_NODE_ID = "HCM_MARKET"

# Weather bulletin thật chỉ nói road/water status cho node đó, không có khái niệm "region"
# (VD "can_tho_to_hcm") như AI2-plan.pdf giả định. Lấy bulletin của cả 2 đầu leg Cần Thơ -> HCM
# và cộng dồn theo hướng "bảo thủ" (blocked nếu 1 trong 2 đầu blocked, risk = max 2 đầu) —
# giống quy ước "lấy max factor" mà data package đề xuất cho weather 2 đầu 1 leg (xem
# VAIC_Data_Simulation_Package_v3_2026-07-18/README.md mục "Time-series lookup").
OUTBOUND_LEG_NODES = (CAN_THO_NODE_ID, HCM_NODE_ID)


def get_data_store(data_dir: str | Path = DEFAULT_DATA_DIR) -> DataStore:
    return load_data(data_dir)


@dataclass(frozen=True)
class CargoProfile:
    commodity_id: str
    name_vi: str
    time_sensitivity: float  # 0..1, xem README mục convert từ perishability_level
    max_safe_wait_hours: float
    needs_reefer: bool
    water_ok: bool
    compatible_vehicle_types: tuple[str, ...]
    value_vnd_per_kg: float
    loss_pct_per_hour: float


@lru_cache(maxsize=8)
def build_cargo_profiles(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, CargoProfile]:
    store = get_data_store(data_dir)
    profiles: dict[str, CargoProfile] = {}
    for commodity_id, row in store.commodities.items():
        perishability_level = int(row["perishability_level"])
        profiles[commodity_id] = CargoProfile(
            commodity_id=commodity_id,
            name_vi=row["name_vi"],
            # Assumption ghi rõ trong README: time_sensitivity = perishability_level / 5.
            time_sensitivity=round(perishability_level / 5.0, 4),
            # Assumption: max_hold_hours canonical (toàn hành trình) được dùng thẳng làm ngân
            # sách chờ tại Cần Thơ — có thể lạc quan vì shipment đã tốn thời gian đi từ hub.
            max_safe_wait_hours=float(row["max_hold_hours"]),
            needs_reefer=bool(row["needs_reefer"]),
            water_ok=bool(row["water_ok"]),
            compatible_vehicle_types=tuple(row["compatible_vehicle_types"]),
            value_vnd_per_kg=float(row["value_vnd_per_kg"]),
            loss_pct_per_hour=float(row["loss_pct_per_hour"]),
        )
    return profiles


def get_cargo_profile(commodity_id: str, data_dir: str | Path = DEFAULT_DATA_DIR) -> CargoProfile | None:
    return build_cargo_profiles(data_dir).get(commodity_id)


@dataclass(frozen=True)
class WeatherAssessment:
    decision_ts: datetime
    road_blocked: bool
    water_blocked: bool
    risk: float  # 0..1, max(max_flood_risk_idx) của các node xét
    bulletin_refs: tuple[str, ...]
    missing_nodes: tuple[str, ...]


def _bulletin_covers(bulletin: dict[str, Any], decision_ts: datetime) -> bool:
    return bulletin["_valid_from_dt"] <= decision_ts <= bulletin["_valid_to_dt"]


def get_outbound_weather_assessment(
    store: DataStore,
    decision_ts: datetime,
    nodes: tuple[str, ...] = OUTBOUND_LEG_NODES,
) -> WeatherAssessment:
    road_blocked = False
    water_blocked = False
    risk = 0.0
    refs: list[str] = []
    missing: list[str] = []

    for node_id in nodes:
        covering = [
            b for b in store.weather_bulletins
            if b["node_id"] == node_id and _bulletin_covers(b, decision_ts)
        ]
        if not covering:
            missing.append(node_id)
            continue
        bulletin = covering[-1]
        refs.append(bulletin["bulletin_id"])
        if bulletin["road_status"] == "closed":
            road_blocked = True
        if bulletin["water_navigation_status"] == "closed":
            water_blocked = True
        risk = max(risk, float(bulletin["max_flood_risk_idx"]))

    return WeatherAssessment(
        decision_ts=decision_ts,
        road_blocked=road_blocked,
        water_blocked=water_blocked,
        risk=risk,
        bulletin_refs=tuple(refs),
        missing_nodes=tuple(missing),
    )


def get_fleet_bootstrap_rows(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    at_node: str = CAN_THO_NODE_ID,
) -> list[dict[str, Any]]:
    """Vehicle canonical hiện đang ở Cần Thơ, dùng để bootstrap state_store khi service khởi
    động (trước khi có event vehicle_status_changed thật). Không dùng lại làm real-time state
    — xem README mục fleet."""

    store = get_data_store(data_dir)
    return [row for row in store.fleet if row["current_node_id"] == at_node]
