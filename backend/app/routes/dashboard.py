from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.routes.auth import current_user
from app.services.ai1_client import run_optimizer
from app.services.ai2_client import get_deliveries, get_jobs
from app.services.map_data import errors, fleet_rows, latest_weather, live_savings_kpis, map_payload_for_user, route_options_for_hub, logistics_overview_payload
from app.database import engine
from app.models import Order
from app.order_times import effective_harvested_at


from app.mappings import enrich_order_payload, LOGISTICS_MAPPING, ENTERPRISE_MAPPING, get_business_name, get_provider_name


router = APIRouter(prefix="/dashboard")
TRACKING_PATH = Path("data/session_orders.json")

ROLE_SECTIONS = {
    "business": ["business_shipment_form", "business_recommendations", "business_tracking"],
    "logistics": ["logistics_overview", "logistics_orders", "logistics_fleet", "logistics_jobs", "logistics_deliveries"],
    "admin": [
        "admin_inventory",
        "admin_weather",
        "admin_dispatch",
        "admin_simulation",
        "admin_logs",
        "admin_orders",
        "admin_operations",
        "admin_logistics",
        "business_shipment_form",
        "logistics_fleet",
    ],
}

SECTION_LABELS = {
    "business_shipment_form": "Shipment Form",
    "business_recommendations": "Recommendations/Analytics",
    "business_tracking": "Tracking",
    "logistics_overview": "Overview",
    "logistics_fleet": "Fleet",
    "logistics_jobs": "Jobs",
    "logistics_deliveries": "Deliveries",
    "admin_inventory": "Inventory",
    "admin_weather": "Weather",
    "admin_dispatch": "Dispatch",
    "admin_simulation": "Simulation",
    "admin_logs": "Logs/Analytics",
    "admin_orders": "Orders",
    "admin_operations": "Operations",
    "admin_logistics": "Logistics Partners",
}

DEFAULT_SECTION = {
    "business": "business_shipment_form",
    "enterprise": "business_shipment_form",
    "logistics": "logistics_overview",
    "admin": "admin_inventory"
}

REASON_LABELS = {
    "hang_khong_phu_hop_duong_thuy": "Loại hàng không phù hợp vận chuyển đường thủy.",
    "muc_nuoc_khong_an_toan": "Mực nước hoặc điều kiện thủy văn chưa an toàn.",
    "khong_co_phuong_tien_phu_hop": "Chưa có phương tiện phù hợp về tải trọng/trạng thái.",
    "vuot_deadline": "Không đáp ứng được hạn giao hàng.",
    "missing_weather": "Thiếu dữ liệu thời tiết gần thời điểm quyết định.",
}

HUB_OPTIONS = [
    {"value": "HUB_VITHANH", "label": "Hub Vị Thanh"},
    {"value": "HUB_LONGXUYEN", "label": "Hub Long Xuyên"},
    {"value": "HUB_SOCTRANG", "label": "Hub Sóc Trăng"},
    {"value": "HUB_VINHLONG", "label": "Hub Vĩnh Long"},
]

COMMODITY_OPTIONS = [
    "COM_RICE",
    "COM_PANGASIUS",
    "COM_SHRIMP",
    "COM_POMELO",
    "COM_VEGETABLE",
    "COM_PURPLE_ONION",
]


class ShipmentPayload(BaseModel):
    hub_id: str
    commodity_id: str | None = None
    loai_hang: str = ""
    khoi_luong_kg: float = Field(gt=0)
    timestamp: str
    harvested_at: str | None = None
    delivery_deadline: str | None = None


def model_from_dict(model_cls, data: dict[str, Any]):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def allowed_sections(role: str) -> list[str]:
    r = "business" if role == "enterprise" else role
    return ROLE_SECTIONS[r]


def menu_for(role: str) -> list[dict[str, str]]:
    return [{"id": item, "label": SECTION_LABELS[item]} for item in allowed_sections(role)]


def load_tracking(username: str) -> list[dict[str, Any]]:
    if not TRACKING_PATH.exists():
        return []
    try:
        data = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
        return data.get(username, [])
    except Exception:
        return []


def save_tracking(username: str, item: dict[str, Any]) -> None:
    data = {}
    if TRACKING_PATH.exists():
        try:
            data = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.setdefault(username, []).insert(0, item)
    data[username] = data[username][:50]
    TRACKING_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKING_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def layer2_forecast_payload() -> dict[str, Any]:
    """Return the live Layer 2 forecast for both outbound modes.

    The admin dashboards already use this authenticated dashboard payload, so
    exposing the forecast here keeps the UI on the same durable backend state
    as the dispatch supervisor without changing Layer 2 model logic.
    """
    from app.ai.forecast_dispatch import decision_engine
    from app.ai.forecast_dispatch.enums import Mode
    from app.routes.layer2 import DEFAULT_CONFIG, store

    generated_at = datetime.now(timezone.utc)
    modes: dict[str, Any] = {}
    for mode in (Mode.ROAD, Mode.WATER):
        try:
            result = decision_engine.evaluate(store, generated_at, mode, DEFAULT_CONFIG)
            forecast = result.forecast
            modes[mode.value] = {
                "mode": mode.value,
                "available": True,
                "decision": result.decision.value,
                "reason_codes": [code.value for code in result.reason_codes],
                "explanation": result.explanation,
                "current_load_kg": result.current_load_kg,
                "waiting_shipment_count": result.waiting_shipment_count,
                "fill_ratio": result.fill_ratio,
                "selected_vehicle": (
                    {
                        "vehicle_id": result.selected_vehicle.vehicle_id,
                        "capacity_kg": result.selected_vehicle.capacity_kg,
                    }
                    if result.selected_vehicle else None
                ),
                "priority_score": (
                    {
                        "fill_component": result.priority_score.fill_component,
                        "urgency_component": result.priority_score.urgency_component,
                        "weather_component": result.priority_score.weather_component,
                        "total_score": result.priority_score.total_score,
                    }
                    if result.priority_score else None
                ),
                "bucket_minutes": forecast.bucket_minutes,
                "horizon_hours": forecast.horizon_hours,
                "predicted_full_load_time": (
                    forecast.predicted_full_load_time.isoformat()
                    if forecast.predicted_full_load_time else None
                ),
                "predicted_load_kg": forecast.predicted_load_kg,
                "confidence": forecast.confidence,
                "buckets": [
                    {
                        "timestamp": bucket.timestamp.isoformat(),
                        "known_inbound_kg": bucket.known_inbound_kg,
                        "predicted_unknown_kg": bucket.predicted_unknown_kg,
                        "predicted_cumulative_load_kg": bucket.predicted_cumulative_load_kg,
                    }
                    for bucket in forecast.buckets
                ],
            }
        except Exception as exc:
            modes[mode.value] = {
                "mode": mode.value,
                "available": False,
                "error": str(exc),
                "buckets": [],
            }

    return {
        "available": any(item.get("available", True) for item in modes.values()),
        "generated_at": generated_at.isoformat(),
        "modes": modes,
    }


def prepare_section_context(user: dict[str, Any], section: str) -> dict[str, Any]:
    if section == "business_tracking":
        return {"tracking": load_tracking(user["username"])}
    if section == "logistics_overview":
        jobs, live = get_jobs()
        deliveries = get_deliveries()
        return {
            "logistics_overview": logistics_overview_payload(jobs, deliveries),
            "ai2_live": live,
        }
    if section == "logistics_fleet":
        return {"fleet": fleet_rows(), "status_filter": ""}
    if section == "logistics_jobs":
        jobs, live = get_jobs()
        return {"jobs": jobs, "ai2_live": live}
    if section == "logistics_deliveries":
        return {"deliveries": get_deliveries()}
    if section == "admin_inventory":
        payload = map_payload_for_user(user)
        return {
            "kpis": live_savings_kpis(),
            "map_payload": payload,
            "map_payload_json": json.dumps(payload),
            "forecast": layer2_forecast_payload(),
        }
    if section == "admin_orders":
        from sqlmodel import select
        from app.models import Order, Vehicle
        with Session(engine) as session:
            orders = session.exec(select(Order)).all()
            enriched = [enrich_order_payload(o, session) for o in orders]
            
            vehicles = session.exec(select(Vehicle)).all()
            providers_list = []
            for i in range(1, 6):
                email = f"logistics{i}@vaic.vn"
                p_name = LOGISTICS_MAPPING.get(email)
                p_vehicles = [v for v in vehicles if v.provider_id == i or (v.provider_id and str(v.provider_id) == str(i))]
                providers_list.append({
                    "id": str(i),
                    "name": p_name,
                    "modes": ["road", "water"] if i in [3, 4] else ["road"],
                    "available_vehicles": len([v for v in p_vehicles if v.status == "available"]),
                    "ontime_rate": 95 + i,
                    "status": "available" if len([v for v in p_vehicles if v.status == "available"]) > 0 else "busy"
                })
            return {"orders": enriched, "providers": providers_list}
    if section == "admin_operations":
        from sqlmodel import select
        from app.models import Order, DispatchOrder, SystemLog, User, Vehicle
        with Session(engine) as session:
            created_orders = session.exec(select(Order).where(Order.state == "created")).all()
            queue = []
            for o in created_orders:
                enriched = enrich_order_payload(o, session)
                from app.services.ai1_client import run_optimizer
                try:
                    result = run_optimizer({
                        "hub_id": o.hub_id,
                        "commodity_id": o.commodity_id,
                        "loai_hang": o.loai_hang,
                        "khoi_luong_kg": o.khoi_luong_kg,
                        "timestamp": o.timestamp
                    })
                    rec_route = result.get("recommended_route")
                    suggested_p = "Mekong Logistics"
                    if rec_route in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"]:
                        suggested_p = "Delta Waterway"
                    elif rec_route in ["C_WATER_ROAD_VIA_CT"]:
                        suggested_p = "Cần Thơ Trans"
                except:
                    rec_route = "B_ROAD_VIA_CT"
                    suggested_p = "Mekong Logistics"
                    
                queue.append({
                    "priority": "high" if o.khoi_luong_kg > 10000 else "medium" if o.khoi_luong_kg > 5000 else "low",
                    "order_id": f"ORD{o.id:03d}" if o.id else "ORD-NEW",
                    "db_id": o.id,
                    "business_name": enriched["business_name"],
                    "commodity": enriched["commodity"],
                    "deadline": o.delivery_deadline or "N/A",
                    "recommended_route": rec_route,
                    "capacity_ton": round(o.khoi_luong_kg / 1000.0, 1),
                    "suggested_provider": suggested_p,
                    "reason": "Large volume - waiting for waterway" if rec_route in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else "Awaiting assignment",
                })
            
            active_orders = session.exec(select(Order).where(Order.state.in_(["routed_to_can_tho", "arrived_waiting", "dispatched"]))).all()
            active_shipments = []
            for o in active_orders:
                enriched = enrich_order_payload(o, session)
                from app.simulation import SYSTEM_CLOCK
                from datetime import timezone
                try:
                    start_time = datetime.fromisoformat(o.timestamp)
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    end_time = datetime.fromisoformat(o.eta_can_tho) if o.eta_can_tho else start_time
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)
                    total_sec = (end_time - start_time).total_seconds()
                    elapsed_sec = (SYSTEM_CLOCK - start_time).total_seconds()
                    progress = max(0.0, min(1.0, elapsed_sec / total_sec if total_sec > 0 else 1.0))
                except:
                    progress = 0.5
                
                status_map = {
                    "routed_to_can_tho": "on_track",
                    "arrived_waiting": "at_hub",
                    "dispatched": "on_track",
                }
                
                active_shipments.append({
                    "id": f"ORD{o.id:03d}",
                    "db_id": o.id,
                    "order_id": f"ORD{o.id:03d}",
                    "business_name": enriched["business_name"],
                    "commodity": enriched["commodity"],
                    "provider_name": enriched["provider_name"] or "Mekong Logistics",
                    "route": o.selected_route_id,
                    "progress": enriched["progress"],
                    "eta": o.eta_can_tho or "N/A",
                    "status": status_map.get(o.state, "on_track")
                })
                
            exceptions = []
            logs = session.exec(select(SystemLog).where(SystemLog.level == "ERROR")).all()
            for log in logs:
                exceptions.append({
                    "id": f"EX-{log.id}",
                    "severity": "critical",
                    "type": "delayed",
                    "order_id": "ORD001",
                    "business_name": "Cửu Long Rice Co.",
                    "created_at": log.timestamp,
                    "description": log.message,
                    "resolved": False
                })
            
            vehicles = session.exec(select(Vehicle)).all()
            users = session.exec(select(User)).all()
            logistics_users = {
                user.email: user
                for user in users
                if user.role == "logistics"
            }
            all_dispatches = session.exec(select(DispatchOrder)).all()
            active_dispatches = [d for d in all_dispatches if d.status != "completed"]

            waiting_orders = session.exec(
                select(Order).where(Order.state == "arrived_waiting")
            ).all()
            hub_waiting_weight_kg = sum(
                order.actual_weight_kg or order.khoi_luong_kg
                for order in waiting_orders
            )
            dispatch_load_by_mode = {
                "road": sum(d.total_weight_kg for d in active_dispatches if d.outbound_mode == "road"),
                "water": sum(d.total_weight_kg for d in active_dispatches if d.outbound_mode == "water"),
            }
            fleet_capacity_by_mode = {
                mode: sum(v.capacity_kg for v in vehicles if v.mode == mode)
                for mode in ("road", "water")
            }
            available_capacity_by_mode = {
                mode: sum(
                    v.capacity_kg
                    for v in vehicles
                    if v.mode == mode and v.status == "available" and v.location == "can_tho"
                )
                for mode in ("road", "water")
            }
            providers_list = []
            for i in range(1, 6):
                email = f"logistics{i}@vaic.vn"
                p_name = LOGISTICS_MAPPING.get(email)
                provider_user = logistics_users.get(email)
                provider_id = provider_user.id if provider_user else i
                p_vehicles = [v for v in vehicles if v.provider_id == provider_id]
                total_veh = len(p_vehicles)
                avail_veh = len([
                    v for v in p_vehicles
                    if v.status == "available" and v.location == "can_tho"
                ])
                active_vehicle_ids = {
                    v.license_plate
                    for v in p_vehicles
                    if v.status in ["en_route", "in_transit"]
                }
                active_ord = len({
                    d.proposal_id
                    for d in active_dispatches
                    if d.vehicle_id in active_vehicle_ids
                })
                total_capacity_ton = sum(v.capacity_kg for v in p_vehicles) / 1000.0
                active_capacity_ton = sum(
                    v.capacity_kg for v in p_vehicles
                    if v.status in ["en_route", "in_transit"]
                ) / 1000.0
                available_capacity_ton = sum(
                    v.capacity_kg for v in p_vehicles
                    if v.status == "available" and v.location == "can_tho"
                ) / 1000.0
                modes = sorted({v.mode for v in p_vehicles})
                providers_list.append({
                    "id": str(i),
                    "name": p_name,
                    "modes": modes,
                    "fleet_size": total_veh,
                    "active_orders": active_ord,
                    "available_vehicles": avail_veh,
                    "total_capacity_ton": round(total_capacity_ton, 2),
                    "active_capacity_ton": round(active_capacity_ton, 2),
                    "available_capacity_ton": round(available_capacity_ton, 2),
                    "utilization": int((active_capacity_ton / total_capacity_ton * 100)) if total_capacity_ton > 0 else 0,
                    "ontime_rate": 95 + i,
                    "status": "available" if avail_veh > 0 else "busy"
                })
                
            return {
                "queue": queue,
                "active_shipments": active_shipments,
                "exceptions": exceptions,
                "providers": providers_list,
                "kpis": live_savings_kpis(),
                "forecast": layer2_forecast_payload(),
                "capacity": {
                    "hub": {
                        "used_ton": round(hub_waiting_weight_kg / 1000.0, 2),
                        "capacity_ton": None,
                        "capacity_configured": False,
                        "waiting_orders": len(waiting_orders),
                    },
                    "transport": {
                        mode: {
                            "used_ton": round(dispatch_load_by_mode[mode] / 1000.0, 2),
                            "total_ton": round(fleet_capacity_by_mode[mode] / 1000.0, 2),
                            "available_ton": round(available_capacity_by_mode[mode] / 1000.0, 2),
                        }
                        for mode in ("road", "water")
                    },
                    "queue": {
                        "waiting_orders": len(waiting_orders),
                        "waiting_volume_ton": round(hub_waiting_weight_kg / 1000.0, 2),
                        "next_dispatch_hours": None,
                    },
                }
            }
    if section == "admin_logistics":
        from sqlmodel import select
        from app.models import Vehicle
        with Session(engine) as session:
            vehicles = session.exec(select(Vehicle)).all()
            providers_list = []
            for i in range(1, 6):
                email = f"logistics{i}@vaic.vn"
                p_name = LOGISTICS_MAPPING.get(email)
                p_vehicles = [v for v in vehicles if v.provider_id == i or (v.provider_id and str(v.provider_id) == str(i))]
                providers_list.append({
                    "id": str(i),
                    "name": p_name,
                    "email": email,
                    "modes": ["road", "water"] if i in [3, 4] else ["road"],
                    "fleet_size": len(p_vehicles),
                    "available_vehicles": len([v for v in p_vehicles if v.status == "available"]),
                    "active_orders": len([v for v in p_vehicles if v.status in ["en_route", "in_transit"]]),
                    "ontime_rate": 95 + i,
                    "status": "available" if len([v for v in p_vehicles if v.status == "available"]) > 0 else "busy"
                })
            return {"providers": providers_list}
    if section == "admin_weather":
        return {"weather": latest_weather()}
    if section == "admin_dispatch":
        jobs, live = get_jobs()
        return {"jobs": jobs, "ai2_live": live}
    if section == "admin_logs":
        kpis = live_savings_kpis()
        return {"errors": errors(), "kpis": kpis, "route_counts_json": json.dumps(kpis["route_counts"])}
    return {}


def api_context(user: dict[str, Any], section: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user": user,
        "role": user["role"],
        "section": section,
        "section_label": SECTION_LABELS[section],
        "menu": menu_for(user["role"]),
        "reason_labels": REASON_LABELS,
        "hub_options": HUB_OPTIONS,
        "commodity_options": COMMODITY_OPTIONS,
    }
    payload.update(prepare_section_context(user, section))
    if extra:
        payload.update(extra)
    return payload


def api_user(request: Request) -> dict[str, Any] | JSONResponse:
    user = current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.email,
        "role": user.role
    }



@router.get("/api/view")
def api_view(request: Request, section: str | None = None, status_filter: str = ""):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    section = section or DEFAULT_SECTION[user["role"]]
    if section not in allowed_sections(user["role"]):
        section = DEFAULT_SECTION[user["role"]]
    extra: dict[str, Any] = {}
    if section == "logistics_fleet":
        rows = fleet_rows()
        if status_filter:
            rows = [row for row in rows if row["status"] == status_filter]
        extra = {"fleet": rows, "status_filter": status_filter}
    return api_context(user, section, extra)


@router.post("/api/shipment")
async def api_submit_shipment(request: Request):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] not in {"enterprise", "admin"}:
        return JSONResponse({"error": "Only enterprise users can create orders"}, status_code=403)
    payload = model_from_dict(ShipmentPayload, await request.json())
    input_data = {
        "hub_id": payload.hub_id,
        "commodity_id": payload.commodity_id or None,
        "loai_hang": payload.loai_hang,
        "khoi_luong_kg": payload.khoi_luong_kg,
        "timestamp": payload.timestamp,
        "harvested_at": payload.harvested_at,
        "deadline_ts": payload.delivery_deadline,
    }
    result = run_optimizer(input_data)
    route_map = route_options_for_hub(result["hub_id"])
    with Session(engine) as session:
        created_at = datetime.now().isoformat(timespec="seconds")
        order = Order(
            hub_id=payload.hub_id,
            commodity_id=payload.commodity_id,
            loai_hang=payload.loai_hang,
            khoi_luong_kg=payload.khoi_luong_kg,
            timestamp=payload.timestamp,
            created_at=created_at,
            harvested_at=effective_harvested_at(payload.harvested_at, created_at),
            delivery_deadline=payload.delivery_deadline,
            user_id=user["id"],
            route_options_json=json.dumps(result.get("phuong_an", []), ensure_ascii=False),
            selected_route_geometry_json=json.dumps(route_map.get("routes", {}), ensure_ascii=False),
            optimizer_version="route_optimizer_v1",
        )
        session.add(order)
        session.commit()
    save_tracking(
        user["username"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input": input_data,
            "recommended_route": result["recommended_route"],
            "khuyen_nghi": result["khuyen_nghi"],
            "routes": result["phuong_an"],
        },
    )
    section = "business_recommendations" if user["role"] != "admin" else "admin_simulation"
    route_map["activeRoute"] = result["recommended_route"]
    return api_context(user, section, {"result": result, "input_data": input_data, "route_map": route_map})


@router.get("/api/map-data")
def api_map_data(request: Request):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(map_payload_for_user(user))


class AssignProviderPayload(BaseModel):
    order_id: str
    provider_id: str

@router.post("/api/assign-provider")
async def api_assign_provider(payload: AssignProviderPayload, request: Request):
    actor = current_user(request)
    if actor is None or actor.role != "admin":
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    from app.models import Vehicle, SystemLog
    from app.simulation import SYSTEM_CLOCK
    from datetime import timedelta
    from app.routes.websocket import ws_manager
    from app.state import state_manager
    
    order_id_str = payload.order_id.replace("ORD", "")
    try:
        db_id = int(order_id_str)
    except:
        return JSONResponse({"error": "Invalid order ID format"}, status_code=400)
        
    with Session(engine) as session:
        order = session.get(Order, db_id)
        if not order:
            return JSONResponse({"error": "Order not found"}, status_code=404)
            
        route_id = order.selected_route_id or "B_ROAD_VIA_CT"
        inbound_mode = "water" if route_id in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else "road"
        
        p_id = int(payload.provider_id)
        from app.models import User
        provider_user = session.exec(select(User).where(User.email == f"logistics{p_id}@vaic.vn")).first()
        actual_provider_id = provider_user.id if provider_user else p_id
        if not provider_user or provider_user.role != "logistics":
            return JSONResponse({"error": "Invalid logistics provider"}, status_code=400)

        veh = session.exec(select(Vehicle).where(
            Vehicle.provider_id == actual_provider_id,
            Vehicle.status == "available",
            Vehicle.mode == inbound_mode
        )).first()
        if not veh:
            return JSONResponse({"error": "No available vehicle for this inbound route"}, status_code=409)
            
        if veh:
            order.assigned_vehicle_id = veh.license_plate
            order.assigned_provider_id = veh.provider_id
            order.provider_assignment_status = "assigned"
            order.provider_assigned_at = SYSTEM_CLOCK.isoformat()
            veh.status = "en_route"
            veh.location = order.hub_id
            session.add(veh)
            
        order.state = "routed_to_can_tho"
        eta_hours = order.selected_route_eta_hours or 2.0
        order.eta_can_tho = (SYSTEM_CLOCK + timedelta(hours=eta_hours)).isoformat()
        
        session.add(order)
        
        timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"Admin assigned provider: Order #{db_id} assigned to provider ID {payload.provider_id} via vehicle {veh.license_plate if veh else 'None'}."
        session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
        
        session.commit()
        
    updated_state = await state_manager.get_state()
    from app.services.ai2_client import get_deliveries, get_jobs
    from app.services.map_data import logistics_overview_payload, fleet_rows
    
    jobs, live = get_jobs()
    deliveries = get_deliveries()
    logistics = logistics_overview_payload(jobs, deliveries)
    fleet = fleet_rows()
    
    payload_ws = {
        "event": "STATE_UPDATE",
        "system_clock": SYSTEM_CLOCK.isoformat(),
        "data": updated_state.model_dump(mode="json"),
        "logistics_overview": logistics,
        "fleet": fleet,
        **updated_state.model_dump(mode="json")
    }
    await ws_manager.broadcast_event("STATE_UPDATE", payload_ws)
    return {"status": "success"}


class ApproveRoutePayload(BaseModel):
    order_id: str

@router.post("/api/approve-route")
async def api_approve_route(payload: ApproveRoutePayload, request: Request):
    actor = current_user(request)
    if actor is None or actor.role != "admin":
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    from app.models import Vehicle, SystemLog
    from app.simulation import SYSTEM_CLOCK
    from datetime import timedelta
    from app.services.ai1_client import run_optimizer
    from app.routes.websocket import ws_manager
    from app.state import state_manager
    
    order_id_str = payload.order_id.replace("ORD", "")
    try:
        db_id = int(order_id_str)
    except:
        return JSONResponse({"error": "Invalid order ID format"}, status_code=400)
        
    with Session(engine) as session:
        order = session.get(Order, db_id)
        if not order:
            return JSONResponse({"error": "Order not found"}, status_code=404)
            
        result = run_optimizer({
            "hub_id": order.hub_id,
            "commodity_id": order.commodity_id,
            "loai_hang": order.loai_hang,
            "khoi_luong_kg": order.khoi_luong_kg,
            "timestamp": order.timestamp
        })
        rec_route = result.get("recommended_route")
        selected_option = next(
            (opt for opt in result.get("phuong_an", []) if opt.get("route_code") == rec_route),
            None
        )
        
        order.selected_route_id = rec_route
        if selected_option:
            order.selected_route_cost_vnd = selected_option.get("chi_phi_du_doan_vnd")
            order.selected_route_eta_hours = selected_option.get("thoi_gian_du_kien_gio")
        else:
            order.selected_route_cost_vnd = 55000000.0
            order.selected_route_eta_hours = 2.0
        
        inbound_mode = "water" if rec_route in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else "road"
        provider_idx = 3 if rec_route in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else 1
        
        from app.models import User
        provider_user = session.exec(select(User).where(User.email == f"logistics{provider_idx}@vaic.vn")).first()
        actual_provider_id = provider_user.id if provider_user else provider_idx

        veh = session.exec(select(Vehicle).where(
            Vehicle.provider_id == actual_provider_id,
            Vehicle.status == "available",
            Vehicle.mode == inbound_mode
        )).first()
        if not veh:
            return JSONResponse({"error": "No available vehicle for this inbound route"}, status_code=409)
            
        if veh:
            order.assigned_vehicle_id = veh.license_plate
            order.assigned_provider_id = veh.provider_id
            order.provider_assignment_status = "assigned"
            order.provider_assigned_at = SYSTEM_CLOCK.isoformat()
            veh.status = "en_route"
            veh.location = order.hub_id
            session.add(veh)
            
        order.state = "routed_to_can_tho"
        order.eta_can_tho = (SYSTEM_CLOCK + timedelta(hours=order.selected_route_eta_hours)).isoformat()
        
        session.add(order)
        
        timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"Admin auto-assigned route: Order #{db_id} routed via {rec_route} using vehicle {veh.license_plate if veh else 'None'}."
        session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
        
        session.commit()
        
    updated_state = await state_manager.get_state()
    from app.services.ai2_client import get_deliveries, get_jobs
    from app.services.map_data import logistics_overview_payload, fleet_rows
    
    jobs, live = get_jobs()
    deliveries = get_deliveries()
    logistics = logistics_overview_payload(jobs, deliveries)
    fleet = fleet_rows()
    
    payload_ws = {
        "event": "STATE_UPDATE",
        "system_clock": SYSTEM_CLOCK.isoformat(),
        "data": updated_state.model_dump(mode="json"),
        "logistics_overview": logistics,
        "fleet": fleet,
        **updated_state.model_dump(mode="json")
    }
    await ws_manager.broadcast_event("STATE_UPDATE", payload_ws)
    return {"status": "success"}
