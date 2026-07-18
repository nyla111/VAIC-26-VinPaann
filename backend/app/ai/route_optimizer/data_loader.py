from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


import os

DEFAULT_DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        str(
            Path(__file__).resolve().parents[3]
            / "data"
            / "generated"
            / "three_year"
            / "csv_adapted"
        ),
    )
)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _as_bool(value: str | None) -> bool:
    return str(value).lower() == "true"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class DataStore:
    data_dir: Path
    nodes: dict[str, dict[str, Any]]
    legs: dict[str, dict[str, Any]]
    commodities: dict[str, dict[str, Any]]
    orders: dict[str, dict[str, Any]]  # Giữ lại để tránh lỗi định nghĩa type nhưng truyền rỗng
    weather: dict[tuple[str, str], dict[str, Any]]
    weather_by_node: dict[str, list[dict[str, Any]]]
    fleet: list[dict[str, Any]]
    fuel_prices: dict[str, list[dict[str, Any]]]
    freight_rates: dict[tuple[str, str], list[dict[str, Any]]]
    weather_bulletins: list[dict[str, Any]]


@lru_cache(maxsize=8)
def load_data(data_dir: str | Path = DEFAULT_DATA_DIR) -> DataStore:
    data_dir = Path(data_dir)
    nodes = {r["node_id"]: r for r in _read_csv(data_dir / "nodes.csv")}

    legs: dict[str, dict[str, Any]] = {}
    for r in _read_csv(data_dir / "legs.csv"):
        r["distance_km"] = float(r["distance_km"])
        r["duration_hr_base"] = float(r["duration_hr_base"])
        r["active"] = _as_bool(r["active"])
        legs[r["leg_id"]] = r

    commodities: dict[str, dict[str, Any]] = {}
    for r in _read_csv(data_dir / "commodities.csv"):
        r["loss_pct_per_hour"] = float(r["loss_pct_per_hour"])
        r["value_vnd_per_kg"] = float(r["value_vnd_per_kg"])
        r["needs_reefer"] = _as_bool(r["needs_reefer"])
        r["water_ok"] = _as_bool(r["water_ok"])
        r["compatible_vehicle_types"] = r["compatible_vehicle_types"].split("|")
        commodities[r["commodity_id"]] = r

    # Bỏ qua không load orders.csv tĩnh vì đơn hàng là động
    orders: dict[str, dict[str, Any]] = {}

    weather: dict[tuple[str, str], dict[str, Any]] = {}
    weather_by_node: dict[str, list[dict[str, Any]]] = {}
    for r in _read_csv(data_dir / "weather.csv"):
        r["rainfall_mm"] = float(r["rainfall_mm"])
        r["river_level_m"] = _as_float(r["river_level_m"])
        r["flood_risk_idx"] = float(r["flood_risk_idx"])
        r["road_factor"] = float(r["road_factor"])
        r["water_factor"] = float(r["water_factor"])
        r["_dt"] = parse_ts(r["ts"])
        weather[(r["node_id"], r["ts"])] = r
        weather_by_node.setdefault(r["node_id"], []).append(r)
    for rows in weather_by_node.values():
        rows.sort(key=lambda item: item["_dt"])

    fleet: list[dict[str, Any]] = []
    for r in _read_csv(data_dir / "fleet.csv"):
        r["capacity_ton"] = float(r["capacity_ton"])
        r["cost_fixed_vnd"] = float(r["cost_fixed_vnd"])
        r["cost_per_km_vnd"] = float(r["cost_per_km_vnd"])
        r["speed_kmh"] = float(r["speed_kmh"])
        r["has_reefer"] = _as_bool(r["has_reefer"])
        r["_available_dt"] = parse_ts(r["available_from_ts"])
        fleet.append(r)

    fuel_prices: dict[str, list[dict[str, Any]]] = {}
    for r in _read_csv(data_dir / "fuel_prices.csv"):
        r["price_vnd_per_liter"] = float(r["price_vnd_per_liter"])
        r["_dt"] = parse_ts(r["ts"])
        fuel_prices.setdefault(r["fuel_type"], []).append(r)
    for rows in fuel_prices.values():
        rows.sort(key=lambda item: item["_dt"])

    freight_rates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    freight_path = data_dir / "freight_rates.csv"
    if freight_path.exists():
        for r in _read_csv(freight_path):
            r["fuel_price_vnd_per_liter"] = float(r["fuel_price_vnd_per_liter"])
            r["fuel_cost_factor"] = float(r["fuel_cost_factor"])
            r["rate_vnd_per_ton_km"] = float(r["rate_vnd_per_ton_km"])
            r["fixed_fee_vnd"] = float(r["fixed_fee_vnd"])
            r["demand_idx"] = float(r["demand_idx"])
            r["_dt"] = parse_ts(r["ts"])
            freight_rates.setdefault((r["leg_id"], r["vehicle_type"]), []).append(r)
    for rows in freight_rates.values():
        rows.sort(key=lambda item: item["_dt"])

    weather_bulletins: list[dict[str, Any]] = []
    bulletins_path = data_dir / "weather_bulletins.csv"
    if bulletins_path.exists():
        for r in _read_csv(bulletins_path):
            r["_valid_from_dt"] = parse_ts(r["valid_from"])
            r["_valid_to_dt"] = parse_ts(r["valid_to"])
            weather_bulletins.append(r)

    return DataStore(
        data_dir=data_dir,
        nodes=nodes,
        legs=legs,
        commodities=commodities,
        orders=orders,
        weather=weather,
        weather_by_node=weather_by_node,
        fleet=fleet,
        fuel_prices=fuel_prices,
        freight_rates=freight_rates,
        weather_bulletins=weather_bulletins,
    )


def nearest_previous(rows: list[dict[str, Any]], decision_ts: datetime, dt_key: str = "_dt") -> dict[str, Any] | None:
    left = 0
    right = len(rows)
    while left < right:
        mid = (left + right) // 2
        if rows[mid][dt_key] <= decision_ts:
            left = mid + 1
        else:
            right = mid
    if left == 0:
        return None
    return rows[left - 1]
