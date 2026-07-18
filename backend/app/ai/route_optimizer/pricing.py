from __future__ import annotations

from datetime import datetime
from typing import Any

from .data_loader import DataStore, nearest_previous
from .normalizers import commodity_loss_value


FUEL_BY_MODE = {
    "road": "diesel_005s",
    "water": "marine_diesel",
}

HANDLING_FEE_PER_KG_VND = 150.0
FREIGHT_RATE_FALLBACKS: list[dict[str, Any]] = []


def _leg_weather_factor(store: DataStore, leg: dict[str, Any], decision_ts: datetime) -> float:
    weather = nearest_previous(store.weather_by_node.get(leg["from_node_id"], []), decision_ts)
    if weather is None:
        return 1.0
    if leg["mode"] == "road":
        return weather["road_factor"]
    return weather["water_factor"]


def _candidate_vehicles(
    store: DataStore,
    mode: str,
    required_weight_kg: float,
    compatible_vehicle_types: list[str],
    decision_ts: datetime,
) -> list[dict[str, Any]]:
    required_ton = required_weight_kg / 1000.0
    return [
        vehicle
        for vehicle in store.fleet
        if vehicle["mode"] == mode
        and vehicle["vehicle_type"] in compatible_vehicle_types
        and vehicle["capacity_ton"] >= required_ton
        and vehicle["status"] == "available"
        and vehicle["_available_dt"] <= decision_ts
    ]


def _fuel_price_ratio(store: DataStore, fuel_type: str, fuel: dict[str, Any]) -> float:
    base_rows = store.fuel_prices.get(fuel_type, [])
    if not base_rows:
        return 1.0
    base_price = base_rows[0]["price_vnd_per_liter"]
    if base_price <= 0:
        return 1.0
    return fuel["price_vnd_per_liter"] / base_price


def _has_ct_transshipment(store: DataStore, leg_ids: list[str]) -> bool:
    return any(
        store.legs[leg_id]["from_node_id"] == "CT_HUB" or store.legs[leg_id]["to_node_id"] == "CT_HUB"
        for leg_id in leg_ids
    )


def _transport_cost_for_leg(
    store: DataStore,
    leg: dict[str, Any],
    vehicle: dict[str, Any],
    khoi_luong_kg: float,
    decision_ts: datetime,
) -> tuple[float | None, str | None, str | None]:
    weather_factor = _leg_weather_factor(store, leg, decision_ts)
    freight = nearest_previous(store.freight_rates.get((leg["leg_id"], vehicle["vehicle_type"]), []), decision_ts)
    if freight is not None:
        weight_ton = khoi_luong_kg / 1000.0
        cost = freight["fixed_fee_vnd"] + freight["rate_vnd_per_ton_km"] * weight_ton * leg["distance_km"]
        return cost * weather_factor, freight["ts"], "freight_rates"

    fuel_type = FUEL_BY_MODE[leg["mode"]]
    fuel = nearest_previous(store.fuel_prices[fuel_type], decision_ts)
    if fuel is None:
        return None, None, None
    fuel_ratio = _fuel_price_ratio(store, fuel_type, fuel)
    cost = leg["distance_km"] * vehicle["cost_per_km_vnd"] * fuel_ratio * weather_factor
    FREIGHT_RATE_FALLBACKS.append(
        {
            "leg_id": leg["leg_id"],
            "vehicle_type": vehicle["vehicle_type"],
            "decision_ts": decision_ts.isoformat(),
            "fallback": "fuel_price_x_fleet_cost_per_km",
        }
    )
    return cost, fuel["ts"], "fuel_fallback"


def price_route(
    store: DataStore,
    leg_ids: list[str],
    commodity_id: str | None,
    loai_hang: str,
    khoi_luong_kg: float,
    adjusted_duration_hr: float,
    decision_ts: datetime,
) -> tuple[float | None, str | None, str | None, dict[str, float] | None]:
    loss_info = commodity_loss_value(commodity_id, loai_hang)
    compatible_types = loss_info.get("compatible_vehicle_types")
    if not compatible_types and commodity_id in store.commodities:
        compatible_types = store.commodities[commodity_id]["compatible_vehicle_types"]
    if not compatible_types:
        compatible_types = ["truck_5t", "truck_15t", "reefer_8t", "boat_50t", "barge_200t", "barge_500t"]

    transport_cost = 0.0
    price_ts = None
    pricing_sources: set[str] = set()
    for leg_id in leg_ids:
        leg = store.legs[leg_id]
        vehicles = _candidate_vehicles(store, leg["mode"], khoi_luong_kg, compatible_types, decision_ts)
        if not vehicles:
            return None, "khong_co_phuong_tien_phu_hop", price_ts, None
        vehicle = min(vehicles, key=lambda item: item["cost_per_km_vnd"])
        leg_cost, leg_price_ts, pricing_source = _transport_cost_for_leg(
            store, leg, vehicle, khoi_luong_kg, decision_ts
        )
        if leg_cost is None:
            return None, "missing_fuel_price", price_ts, None
        price_ts = leg_price_ts or price_ts
        pricing_sources.add(pricing_source or "unknown")
        transport_cost += leg_cost

    spoilage_cost = (
        loss_info["loss_pct_per_hour"]
        / 100.0
        * loss_info["value_vnd_per_kg"]
        * khoi_luong_kg
        * adjusted_duration_hr
    )
    transshipment_fee = HANDLING_FEE_PER_KG_VND * khoi_luong_kg if _has_ct_transshipment(store, leg_ids) else 0.0
    total_cost = transport_cost + spoilage_cost + transshipment_fee
    breakdown = {
        "raw_transport_cost_vnd": round(transport_cost, 2),
        "spoilage_cost_vnd": round(spoilage_cost, 2),
        "transshipment_fee_vnd": round(transshipment_fee, 2),
        "total_cost_vnd": round(total_cost, 2),
        "pricing_source": "|".join(sorted(pricing_sources)),
    }
    return round(total_cost, 2), None, price_ts, breakdown
