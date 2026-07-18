from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from route_optimizer.candidates import build_candidates
from route_optimizer.data_loader import load_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(
    os.getenv(
        "VAIC_DATA_DIR",
        PROJECT_ROOT / "VAIC_Data_Simulation_Package_v3_2026-07-18" / "data" / "generated" / "annual" / "csv",
    )
)
OUTPUT_DIR = PROJECT_ROOT / "route_optimizer" / "output"
REPORTING_WINDOW_DAYS = 30

# Proxy factors used only for dashboard CO2e KPI because the canonical dataset does not
# include observed emissions. KPI totals still come from real orders, route choices, legs,
# distances, and weights.
EMISSION_KG_CO2E_PER_TON_KM = {
    "road": 0.120,
    "water": 0.035,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nodes() -> list[dict[str, Any]]:
    rows = read_csv(DATA_DIR / "nodes.csv")
    return [
        {
            "node_id": r["node_id"],
            "name": r["name_vi"],
            "type": r["node_type"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "on_river": r["on_river"],
        }
        for r in rows
    ]


def legs() -> list[dict[str, Any]]:
    node_lookup = {n["node_id"]: n for n in nodes()}
    items = []
    for r in read_csv(DATA_DIR / "legs.csv"):
        start = node_lookup.get(r["from_node_id"])
        end = node_lookup.get(r["to_node_id"])
        if not start or not end:
            continue
        items.append(
            {
                "leg_id": r["leg_id"],
                "mode": r["mode"],
                "from_node_id": r["from_node_id"],
                "to_node_id": r["to_node_id"],
                "distance_km": float(r["distance_km"]),
                "points": [[start["lat"], start["lon"]], [end["lat"], end["lon"]]],
            }
        )
    return items


def fleet_rows() -> list[dict[str, str]]:
    return read_csv(DATA_DIR / "fleet.csv")


def fleet_by_node() -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in fleet_rows():
        grouped[row["current_node_id"]].append(row)
    node_lookup = {n["node_id"]: n for n in nodes()}
    result = []
    for node_id, rows in grouped.items():
        node = node_lookup.get(node_id)
        if not node:
            continue
        statuses = Counter(r["status"] for r in rows)
        result.append(
            {
                "node_id": node_id,
                "lat": node["lat"],
                "lon": node["lon"],
                "count": len(rows),
                "statuses": dict(statuses),
                "vehicles": rows[:12],
            }
        )
    return result


def latest_weather() -> list[dict[str, Any]]:
    latest: dict[str, dict[str, str]] = {}
    for row in read_csv(DATA_DIR / "weather.csv"):
        latest[row["node_id"]] = row
    return [
        {
            "node_id": node_id,
            "ts": row["ts"],
            "road_factor": float(row["road_factor"]),
            "water_factor": float(row["water_factor"]),
            "alert_level": row["alert_level"],
        }
        for node_id, row in latest.items()
    ]


def optimizer_kpis() -> dict[str, Any]:
    rows = read_csv(OUTPUT_DIR / "all_orders_optimized.csv")
    if not rows:
        return {
            "processed": 0,
            "compared_orders": 0,
            "cost_savings": 0.0,
            "co2_savings_kg": 0.0,
            "co2_savings_ton": 0.0,
            "time_saved_hours": 0.0,
            "time_delta_hours_abs": 0.0,
            "time_saved_pct": 0.0,
            "time_delta_pct_abs": 0.0,
            "time_direction": "faster",
            "baseline_time_hours": 0.0,
            "ai_time_hours": 0.0,
            "reporting_start": "-",
            "reporting_end": "-",
            "route_counts": {},
        }

    parsed_rows = []
    for row in rows:
        if not row.get("timestamp"):
            continue
        parsed_rows.append((row, _parse_ts(row["timestamp"])))
    if not parsed_rows:
        return {
            "processed": 0,
            "compared_orders": 0,
            "cost_savings": 0.0,
            "co2_savings_kg": 0.0,
            "co2_savings_ton": 0.0,
            "time_saved_hours": 0.0,
            "time_delta_hours_abs": 0.0,
            "time_saved_pct": 0.0,
            "time_delta_pct_abs": 0.0,
            "time_direction": "faster",
            "baseline_time_hours": 0.0,
            "ai_time_hours": 0.0,
            "reporting_start": "-",
            "reporting_end": "-",
            "route_counts": {},
            "emission_factors": EMISSION_KG_CO2E_PER_TON_KM,
        }

    reporting_end = max(ts for _, ts in parsed_rows)
    reporting_start = reporting_end - timedelta(days=REPORTING_WINDOW_DAYS)
    window_rows = [
        row
        for row, ts in parsed_rows
        if reporting_start <= ts <= reporting_end and row.get("khuyen_nghi") and row.get("chi_phi_du_doan_vnd")
    ]

    store = load_data(DATA_DIR)
    route_metrics = _route_metrics_by_hub(store)
    order_lookup = {row["order_id"]: row for row in read_csv(DATA_DIR / "orders.csv")}

    cost_savings = 0.0
    co2_savings_kg = 0.0
    baseline_time_hours = 0.0
    ai_time_hours = 0.0
    compared_orders = 0
    route_counts: Counter[str] = Counter()

    for row in window_rows:
        hub_routes = route_metrics.get(row["hub_id"], {})
        baseline = hub_routes.get("A_DIRECT_ROAD")
        selected = hub_routes.get(row["khuyen_nghi"])
        if not baseline or not selected:
            continue
        route_counts[row["khuyen_nghi"]] += 1

        ai_cost = _float(row.get("chi_phi_du_doan_vnd"))
        baseline_cost = _float(row.get("A_DIRECT_ROAD_chi_phi_vnd"))
        if ai_cost is not None and baseline_cost is not None:
            cost_savings += baseline_cost - ai_cost

        order = order_lookup.get(row["order_id"])
        weight_kg = _float(row.get("khoi_luong_kg")) or _float(order.get("weight_kg") if order else None)
        if weight_kg is not None:
            co2_savings_kg += _route_emissions_kg(baseline["segments"], weight_kg) - _route_emissions_kg(
                selected["segments"], weight_kg
            )

        selected_time = _float(row.get("thoi_gian_du_kien_gio"))
        if selected_time is not None:
            baseline_time_hours += baseline["duration_hr_base"]
            ai_time_hours += selected_time

        compared_orders += 1

    time_saved_hours = baseline_time_hours - ai_time_hours
    time_saved_pct = (time_saved_hours / baseline_time_hours * 100) if baseline_time_hours else 0.0
    time_direction = "faster" if time_saved_hours >= 0 else "slower"
    return {
        "processed": len(window_rows),
        "compared_orders": compared_orders,
        "cost_savings": cost_savings,
        "co2_savings_kg": co2_savings_kg,
        "co2_savings_ton": co2_savings_kg / 1000,
        "time_saved_hours": time_saved_hours,
        "time_delta_hours_abs": abs(time_saved_hours),
        "time_saved_pct": time_saved_pct,
        "time_delta_pct_abs": abs(time_saved_pct),
        "time_direction": time_direction,
        "baseline_time_hours": baseline_time_hours,
        "ai_time_hours": ai_time_hours,
        "reporting_start": reporting_start.isoformat(),
        "reporting_end": reporting_end.isoformat(),
        "route_counts": dict(route_counts),
        "emission_factors": EMISSION_KG_CO2E_PER_TON_KM,
    }


def errors() -> list[dict[str, str]]:
    return read_csv(OUTPUT_DIR / "errors.csv")


def map_payload() -> dict[str, Any]:
    return {"nodes": nodes(), "legs": legs(), "fleet": fleet_by_node()}


def _parse_ts(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _float(value: str | float | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _route_metrics_by_hub(store) -> dict[str, dict[str, dict[str, Any]]]:
    hubs = ["HUB_VITHANH", "HUB_LONGXUYEN", "HUB_SOCTRANG", "HUB_VINHLONG"]
    metrics: dict[str, dict[str, dict[str, Any]]] = {}
    for hub_id in hubs:
        metrics[hub_id] = {}
        for candidate in build_candidates(hub_id, store.legs):
            segments = [store.legs[leg_id] for leg_id in candidate.leg_ids]
            metrics[hub_id][candidate.route_code] = {
                "duration_hr_base": candidate.duration_hr_base,
                "distance_km": candidate.distance_km,
                "segments": segments,
            }
    return metrics


def _route_emissions_kg(segments: list[dict[str, Any]], weight_kg: float) -> float:
    weight_ton = weight_kg / 1000
    total = 0.0
    for segment in segments:
        factor = EMISSION_KG_CO2E_PER_TON_KM.get(segment["mode"], 0.0)
        total += float(segment["distance_km"]) * weight_ton * factor
    return total


def route_options_for_hub(hub_id: str) -> dict[str, Any]:
    store = load_data(DATA_DIR)
    node_lookup = {n["node_id"]: n for n in nodes()}
    leg_lookup = {leg["leg_id"]: leg for leg in legs()}
    routes: dict[str, list[dict[str, Any]]] = {}
    for candidate in build_candidates(hub_id, store.legs):
        segments = []
        for leg_id in candidate.leg_ids:
            leg = leg_lookup.get(leg_id)
            if not leg:
                continue
            start = node_lookup.get(leg["from_node_id"])
            end = node_lookup.get(leg["to_node_id"])
            if not start or not end:
                continue
            segments.append(
                {
                    "leg_id": leg["leg_id"],
                    "mode": leg["mode"],
                    "from_node_id": leg["from_node_id"],
                    "to_node_id": leg["to_node_id"],
                    "distance_km": leg["distance_km"],
                    "origin": {"lat": start["lat"], "lon": start["lon"]},
                    "destination": {"lat": end["lat"], "lon": end["lon"]},
                    "points": leg["points"],
                }
            )
        routes[candidate.route_code] = segments
    return {"nodes": nodes(), "fleet": fleet_by_node(), "routes": routes}
