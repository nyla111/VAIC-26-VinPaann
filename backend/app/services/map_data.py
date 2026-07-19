from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

from app.ai.route_optimizer.candidates import build_candidates
from app.ai.route_optimizer.data_loader import load_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(
    os.getenv(
        "VAIC_DATA_DIR",
        PROJECT_ROOT / "data" / "generated" / "three_year" / "csv_adapted",
    )
)
OUTPUT_DIR = PROJECT_ROOT / "app" / "ai" / "route_optimizer" / "output"
REPORTING_WINDOW_DAYS = 30

# Proxy factors used only for dashboard CO2e KPI because the canonical dataset does not
# include observed emissions. KPI totals still come from real orders, route choices, legs,
# distances, and weights.
EMISSION_KG_CO2E_PER_TON_KM = {
    "road": 0.120,
    "water": 0.035,
}

# Curated WGS-84 waypoints for the operating corridors.  The source dataset
# contains distances and endpoints, but not a display polyline.  These
# waypoints keep the visual route on the relevant highway/river corridor
# instead of drawing a misleading straight line between hubs.
GEOGRAPHIC_POLYLINES: dict[str, list[list[float]]] = {
    "LEG_VT_CT_ROAD": [[9.7840, 105.4701], [9.8400, 105.5200], [9.9100, 105.6000], [9.9700, 105.6700], [10.0100, 105.7300], [10.0452, 105.7469]],
    "LEG_LX_CT_ROAD": [[10.3864, 105.4352], [10.3500, 105.5100], [10.3000, 105.6000], [10.2200, 105.6700], [10.1400, 105.7200], [10.0800, 105.7600], [10.0452, 105.7469]],
    "LEG_ST_CT_ROAD": [[9.6025, 105.9739], [9.7100, 105.9400], [9.8300, 105.9000], [9.9300, 105.8600], [9.9900, 105.8300], [10.0200, 105.8100], [10.0452, 105.7469]],
    "LEG_VL_CT_ROAD": [[10.2537, 105.9722], [10.2300, 105.9400], [10.2100, 105.9100], [10.1800, 105.8800], [10.1300, 105.8400], [10.0800, 105.8100], [10.0452, 105.7469]],
    "LEG_VT_HCM_ROAD": [[9.7840, 105.4701], [9.9000, 105.6000], [10.0200, 105.7300], [10.1800, 105.9000], [10.3600, 106.1000], [10.5500, 106.3000], [10.7000, 106.5200], [10.7769, 106.7009]],
    "LEG_LX_HCM_ROAD": [[10.3864, 105.4352], [10.4200, 105.5600], [10.4800, 105.7600], [10.5600, 105.9800], [10.6500, 106.2400], [10.7200, 106.5000], [10.7769, 106.7009]],
    "LEG_ST_HCM_ROAD": [[9.6025, 105.9739], [9.7000, 106.0200], [9.8500, 106.1200], [10.0500, 106.2500], [10.3000, 106.4200], [10.5600, 106.5800], [10.7769, 106.7009]],
    "LEG_VL_HCM_ROAD": [[10.2537, 105.9722], [10.3200, 106.0200], [10.4300, 106.1500], [10.5600, 106.3000], [10.6800, 106.5000], [10.7769, 106.7009]],
    "LEG_VT_CT_WATER": [[9.7840, 105.4701], [9.8200, 105.5100], [9.8800, 105.5800], [9.9400, 105.6500], [9.9800, 105.7000], [10.0100, 105.7400], [10.0452, 105.7469]],
    "LEG_LX_CT_WATER": [[10.3864, 105.4352], [10.3300, 105.4800], [10.2800, 105.5400], [10.2200, 105.6100], [10.1600, 105.6700], [10.1100, 105.7200], [10.0452, 105.7469]],
    "LEG_ST_CT_WATER": [[9.6025, 105.9739], [9.6800, 105.9200], [9.7800, 105.8900], [9.8700, 105.8600], [9.9500, 105.8300], [10.0200, 105.8000], [10.0452, 105.7469]],
    "LEG_VL_CT_WATER": [[10.2537, 105.9722], [10.2200, 105.9400], [10.1900, 105.9000], [10.1500, 105.8600], [10.1100, 105.8300], [10.0700, 105.8100], [10.0452, 105.7469]],
    "LEG_CT_HCM_ROAD": [[10.0452, 105.7469], [10.1000, 105.8400], [10.2000, 105.9500], [10.3200, 106.0600], [10.4300, 106.1500], [10.5200, 106.2400], [10.6100, 106.3700], [10.7000, 106.5200], [10.7769, 106.7009]],
    "LEG_CT_HCM_WATER": [[10.0452, 105.7469], [10.0700, 105.8300], [10.1500, 105.9200], [10.2500, 106.0100], [10.3700, 106.1200], [10.4800, 106.2100], [10.5700, 106.3100], [10.6900, 106.5500], [10.7769, 106.7009]],
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
        points = GEOGRAPHIC_POLYLINES.get(
            r["leg_id"],
            [[start["lat"], start["lon"]], [end["lat"], end["lon"]]],
        )
        items.append(
            {
                "leg_id": r["leg_id"],
                "mode": r["mode"],
                "from_node_id": r["from_node_id"],
                "to_node_id": r["to_node_id"],
                "distance_km": float(r["distance_km"]),
                "points": points,
            }
        )
    return items


def fleet_rows() -> list[dict[str, str]]:
    try:
        from sqlmodel import Session, select
        from app.database import engine
        from app.models import Vehicle

        with Session(engine) as session:
            vehicles = session.exec(select(Vehicle)).all()
            if vehicles:
                return [
                    {
                        "vehicle_id": vehicle.license_plate,
                        "mode": vehicle.mode,
                        "vehicle_type": vehicle.mode,
                        "capacity_ton": str(vehicle.capacity_kg / 1000.0),
                        "status": vehicle.status,
                        "current_node_id": "CT_HUB" if vehicle.location == "can_tho" else vehicle.location,
                        "owner_hub_id": "CT_HUB",
                    }
                    for vehicle in vehicles
                ]
    except Exception:
        pass
    return []


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


def live_savings_kpis() -> dict[str, Any]:
    """Calculate savings from persisted orders, not the demo optimizer CSV.

    Layer 1 stores the route comparison on each order.  Reading that snapshot
    here keeps admin analytics consistent with what was actually offered to an
    enterprise and selected for dispatch.  Orders without both a direct-road
    baseline and a selected route are deliberately excluded instead of being
    assigned an estimated value.
    """
    from datetime import datetime
    from sqlmodel import Session, select
    from app.database import engine
    from app.models import Order

    with Session(engine) as session:
        orders = session.exec(select(Order)).all()

    compared = 0
    cost_savings = 0.0
    baseline_cost = 0.0
    optimized_cost = 0.0
    baseline_time = 0.0
    optimized_time = 0.0
    route_counts: Counter[str] = Counter()
    timestamps: list[datetime] = []

    for order in orders:
        if not order.selected_route_id:
            continue
        try:
            options = json.loads(order.route_options_json or "[]")
        except (TypeError, ValueError):
            options = []
        if not isinstance(options, list):
            continue
        by_code = {
            str(option.get("route_code")): option
            for option in options
            if isinstance(option, dict) and option.get("route_code")
        }
        direct = by_code.get("A_DIRECT_ROAD")
        selected = by_code.get(order.selected_route_id, {})
        direct_cost = _float((direct or {}).get("chi_phi_du_doan_vnd"))
        selected_cost = order.selected_route_cost_vnd
        if selected_cost is None:
            selected_cost = _float(selected.get("chi_phi_du_doan_vnd"))
        if direct_cost is None or selected_cost is None:
            continue

        compared += 1
        baseline_cost += direct_cost
        optimized_cost += selected_cost
        cost_savings += direct_cost - selected_cost
        route_counts[order.selected_route_id] += 1

        direct_time = _float((direct or {}).get("thoi_gian_du_kien_gio"))
        selected_time = order.selected_route_eta_hours
        if selected_time is None:
            selected_time = _float(selected.get("thoi_gian_du_kien_gio"))
        if direct_time is not None and selected_time is not None:
            baseline_time += direct_time
            optimized_time += selected_time
        for value in (order.created_at, order.timestamp):
            if value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    timestamps.append(parsed)
                    break
                except ValueError:
                    continue

    time_delta = baseline_time - optimized_time
    time_pct = time_delta / baseline_time * 100 if baseline_time else 0.0
    return {
        "processed": compared,
        "compared_orders": compared,
        "cost_savings": cost_savings,
        "baseline_cost_vnd": baseline_cost,
        "optimized_cost_vnd": optimized_cost,
        "average_savings_vnd": cost_savings / compared if compared else 0.0,
        "orders_with_savings": compared,
        "savings_source": "live_orders",
        "co2_savings_kg": 0.0,
        "co2_savings_ton": 0.0,
        "time_saved_hours": time_delta,
        "time_delta_hours_abs": abs(time_delta),
        "time_saved_pct": time_pct,
        "time_delta_pct_abs": abs(time_pct),
        "time_direction": "faster" if time_delta >= 0 else "slower",
        "baseline_time_hours": baseline_time,
        "ai_time_hours": optimized_time,
        "reporting_start": min(timestamps).isoformat() if timestamps else "-",
        "reporting_end": max(timestamps).isoformat() if timestamps else "-",
        "route_counts": dict(route_counts),
        "emission_factors": EMISSION_KG_CO2E_PER_TON_KM,
    }


def errors() -> list[dict[str, str]]:
    return read_csv(OUTPUT_DIR / "errors.csv")


def map_payload() -> dict[str, Any]:
    return {"nodes": nodes(), "legs": legs(), "fleet": fleet_by_node()}


def map_payload_for_user(user: Any | None = None) -> dict[str, Any]:
    """Build the live map projection for one authenticated role.

    Geometry is shared across roles, while orders and vehicle markers are
    filtered at the backend.  The frontend therefore cannot accidentally
    broaden an enterprise/provider map by passing a different filter.
    """

    from sqlmodel import Session, select
    from app.database import engine
    from app.models import DispatchOrder, Order, Vehicle
    from app.services.order_views import can_view_order

    if isinstance(user, dict):
        role = user.get("role")
        user_id = user.get("id")
    else:
        role = getattr(user, "role", None) if user is not None else "admin"
        user_id = getattr(user, "id", None) if user is not None else None
    with Session(engine) as session:
        all_vehicles = session.exec(select(Vehicle)).all()
        vehicle_by_plate = {vehicle.license_plate: vehicle for vehicle in all_vehicles}
        all_orders = session.exec(select(Order)).all()
        if role == "admin":
            visible_orders = all_orders
        else:
            visible_orders = [
                order
                for order in all_orders
                if can_view_order(order, user, vehicle_by_plate)
            ]
        visible_order_ids = {order.id for order in visible_orders}

        all_dispatches = session.exec(select(DispatchOrder)).all()
        visible_dispatches = []
        for dispatch in all_dispatches:
            shipment_ids = json.loads(dispatch.shipment_ids_json) if dispatch.shipment_ids_json else []
            numeric_ids = {
                int(shipment_id)
                for shipment_id in shipment_ids
                if str(shipment_id).isdigit()
            }
            dispatch_vehicle = vehicle_by_plate.get(dispatch.vehicle_id)
            if role == "admin" or numeric_ids.intersection(visible_order_ids) or (
                role == "logistics" and dispatch_vehicle and dispatch_vehicle.provider_id == user_id
            ):
                visible_dispatches.append((dispatch, numeric_ids))

        delivery_rows = []
        for dispatch, shipment_ids in visible_dispatches:
            first_order = next(
                (order for order in visible_orders if order.id in shipment_ids),
                None,
            )
            hub_id = first_order.hub_id if first_order else "CT_HUB"
            route_code = (first_order.selected_route_id if first_order else None) or "B_ROAD_VIA_CT"
            delivery_rows.append(
                {
                    "delivery_id": f"JOB-{dispatch.proposal_id}",
                    "order_id": first_order.id if first_order else None,
                    "route_code": route_code,
                    "status": dispatch.status,
                    "eta": dispatch.eta_hcm or dispatch.predicted_full_load_time or "N/A",
                    "hub_id": hub_id,
                    "segments": route_options_for_hub(hub_id)["routes"].get(route_code, []),
                }
            )

        live = logistics_overview_payload([], [
            row for row in delivery_rows if row["status"] != "completed"
        ])

        if role == "admin":
            visible_vehicle_ids = {vehicle.license_plate for vehicle in all_vehicles}
        elif role == "logistics":
            visible_vehicle_ids = {
                vehicle.license_plate
                for vehicle in all_vehicles
                if vehicle.provider_id == user_id
            }
        else:
            visible_vehicle_ids = {
                order.assigned_vehicle_id
                for order in visible_orders
                if order.assigned_vehicle_id
            }
            visible_vehicle_ids.update(
                dispatch.vehicle_id
                for dispatch, _ in visible_dispatches
            )

        live["vehicle_points"] = [
            point
            for point in live.get("vehicle_points", [])
            if point.get("vehicle_id") in visible_vehicle_ids
        ]
        live["active_deliveries"] = [
            row for row in delivery_rows if row["status"] not in {"completed", "hoan_tat"}
        ]
        live["waiting_jobs"] = []
        node_lookup = {node["node_id"]: node for node in nodes()}
        for order in visible_orders:
            if order.state != "arrived_waiting":
                continue
            node = node_lookup.get("CT_HUB")
            if not node:
                continue
            live["waiting_jobs"].append(
                {
                    "job_id": f"ORDER-{order.id}",
                    "shipment_id": str(order.id),
                    "hub_id": order.hub_id,
                    "khoi_luong_tich_luy_hien_tai_kg": order.actual_weight_kg or order.khoi_luong_kg,
                    "quyet_dinh": "WAIT_FOR_PROVIDER" if order.provider_assignment_status == "unassigned" else "WAIT_FOR_DISPATCH",
                    "thoi_gian_de_xuat_chay": order.predicted_full_load_time,
                    "route_code": order.selected_route_id or "B_ROAD_VIA_CT",
                    "lat": node["lat"],
                    "lon": node["lon"],
                }
            )

        visible_vehicle_rows = []
        for group in live.get("fleet", []):
            group["vehicles"] = [
                vehicle
                for vehicle in group.get("vehicles", [])
                if vehicle.get("vehicle_id") in visible_vehicle_ids
            ]
            group["count"] = len(group["vehicles"])
            if group["count"]:
                visible_vehicle_rows.append(group)
        live["fleet"] = visible_vehicle_rows
        live["nodes"] = nodes()
        live["legs"] = legs()
        live["operational"] = True
        live["summary"] = {
            **(live.get("summary") or {}),
            "waiting_jobs": len(live["waiting_jobs"]),
            "active_deliveries": len(live["active_deliveries"]),
        }
        return live


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


def _point_along_segments(segments: list[dict[str, Any]], progress: float) -> tuple[float, float]:
    if not segments:
        return 10.05, 105.75
    weighted = [(segment, max(float(segment.get("distance_km", 0)), 1.0)) for segment in segments]
    total = sum(weight for _, weight in weighted)
    target = min(max(progress, 0.0), 1.0) * total
    traversed = 0.0
    for segment, weight in weighted:
        if traversed + weight >= target:
            local = (target - traversed) / weight
            origin = segment["origin"]
            destination = segment["destination"]
            return (
                origin["lat"] + (destination["lat"] - origin["lat"]) * local,
                origin["lon"] + (destination["lon"] - origin["lon"]) * local,
            )
        traversed += weight
    destination = weighted[-1][0]["destination"]
    return destination["lat"], destination["lon"]


def logistics_overview_payload(jobs: list[dict[str, Any]], deliveries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an operational map using real hubs/fleet and simulation tracking positions."""
    from sqlmodel import Session, select
    from app.database import engine
    from app.models import Order
    from app.simulation import SYSTEM_CLOCK
    from datetime import datetime, timezone

    map_nodes = nodes()
    node_lookup = {node["node_id"]: node for node in map_nodes}
    active_deliveries = [delivery for delivery in deliveries if delivery.get("status") != "hoan_tat"]
    delivery_layers = []
    for index, delivery in enumerate(active_deliveries):
        fallback_hubs = ["HUB_VINHLONG", "HUB_SOCTRANG", "HUB_LONGXUYEN", "HUB_VITHANH"]
        hub_id = delivery.get("hub_id") or fallback_hubs[index % len(fallback_hubs)]
        route_code = delivery.get("route_code", "A_DIRECT_ROAD")
        segments = route_options_for_hub(hub_id)["routes"].get(route_code, [])
        delivery_layers.append({**delivery, "hub_id": hub_id, "segments": segments})

    waiting_jobs = []
    for job in jobs:
        node = node_lookup.get(job.get("hub_id"))
        if node:
            waiting_jobs.append({**job, "lat": node["lat"], "lon": node["lon"]})

    # Fetch active orders from SQLite DB
    with Session(engine) as session:
        inbound_orders = session.exec(
            select(Order).where(Order.state.in_(["routed_to_can_tho", "arrived_waiting"]))
        ).all()

    vehicle_points = []
    moving_index = 0
    for index, vehicle in enumerate(fleet_rows()):
        status = vehicle.get("status", "maintenance")
        node = node_lookup.get(vehicle.get("current_node_id")) or node_lookup.get(vehicle.get("owner_hub_id"))
        if not node:
            continue
        
        # Check if vehicle has an active inbound order
        veh_id = vehicle.get("vehicle_id")
        active_order = next((o for o in inbound_orders if o.assigned_vehicle_id == veh_id), None)
        
        route_progress = None
        delivery_id = None
        ai2_metrics = None
        lat, lon = None, None

        if active_order:
            if active_order.state == "routed_to_can_tho":
                # Interpolate position
                try:
                    start_time = datetime.fromisoformat(active_order.timestamp)
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    end_time = datetime.fromisoformat(active_order.eta_can_tho)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)
                    
                    total_sec = (end_time - start_time).total_seconds()
                    elapsed_sec = (SYSTEM_CLOCK - start_time).total_seconds()
                    p = max(0.0, min(1.0, elapsed_sec / total_sec if total_sec > 0 else 1.0))
                except Exception:
                    p = 0.5

                segments = route_options_for_hub(active_order.hub_id)["routes"].get(active_order.selected_route_id, [])
                lat, lon = _point_along_segments(segments, p)
                status = "in_transit"
                display_status = "in_delivery"
                route_progress = p
                delivery_id = f"ORDER-{active_order.id}"
            else: # arrived_waiting
                # Snap to Can Tho Hub
                ct_node = node_lookup.get("CT_HUB")
                lat, lon = ct_node["lat"], ct_node["lon"]
                status = "available"
                display_status = "arrived_waiting"
                delivery_id = f"ORDER-{active_order.id}"
                
                # Fetch matching job metrics
                matching_job = next((j for j in jobs if j.get("shipment_id") == str(active_order.id)), None)
                ai2_metrics = {
                    "decision": matching_job.get("quyet_dinh") if matching_job else "WAIT",
                    "explanation": matching_job.get("explanation") if matching_job else "Chờ gom thêm hàng...",
                    "reason_codes": matching_job.get("reason_codes") if matching_job else [],
                    "thoi_gian_de_xuat_chay": matching_job.get("thoi_gian_de_xuat_chay") if matching_job else None
                }
        else:
            # Fallback to standard active delivery mapping for outbound trips
            if status in {"en_route", "in_transit"} and delivery_layers:
                delivery = delivery_layers[moving_index % len(delivery_layers)]
                progress = 0.22 + ((moving_index * 17) % 57) / 100
                lat, lon = _point_along_segments(delivery["segments"], progress)
                moving_index += 1
                display_status = "in_delivery"
                delivery_id = delivery.get("delivery_id")
                route_progress = progress
            else:
                lat = node["lat"] + (((index * 7) % 9) - 4) * 0.004
                lon = node["lon"] + (((index * 11) % 9) - 4) * 0.004
                display_status = "available" if status == "available" else "unavailable"

        vehicle_points.append(
            {
                "vehicle_id": vehicle.get("vehicle_id", "Unknown vehicle"),
                "vehicle_type": vehicle.get("vehicle_type", "vehicle"),
                "capacity_ton": vehicle.get("capacity_ton", ""),
                "source_status": status,
                "display_status": display_status,
                "current_node_id": vehicle.get("current_node_id", ""),
                "delivery_id": delivery_id,
                "route_progress": route_progress,
                "lat": lat,
                "lon": lon,
                "ai2_metrics": ai2_metrics
            }
        )

    counts = Counter(vehicle["display_status"] for vehicle in vehicle_points)
    return {
        "nodes": map_nodes,
        "fleet": fleet_by_node(),
        "vehicle_points": vehicle_points,
        "waiting_jobs": waiting_jobs,
        "active_deliveries": delivery_layers,
        "summary": {
            "waiting_jobs": len(waiting_jobs),
            "active_deliveries": len(active_deliveries),
            "available_vehicles": counts["available"],
            "unavailable_vehicles": counts["unavailable"],
        },
        "operational": True,
    }
