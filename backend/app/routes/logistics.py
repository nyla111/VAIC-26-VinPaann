import json
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.routes.auth import current_user
from app.database import engine
from app.models import CargoInventory, Vehicle, DispatchOrder, Order, SystemLog
from app.services.map_data import nodes, legs
from app.services.order_views import can_view_order, order_projection

router = APIRouter(prefix="/api/v1/logistics")


class AcceptOrderPayload(BaseModel):
    vehicle_id: str = Field(min_length=1)


class DispatchOrdersPayload(BaseModel):
    order_ids: list[int] = Field(min_length=1)
    vehicle_id: str = Field(min_length=1)


def _require_logistics(request: Request):
    user = current_user(request)
    if user is None or user.role != "logistics":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def _outbound_mode(order: Order) -> str:
    return "water" if order.selected_route_id in {"D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"} else "road"


def _weight(order: Order) -> float:
    return float(order.actual_weight_kg or order.khoi_luong_kg)


def _cargo_inventory_key(order: Order) -> str:
    if order.commodity_id in {"COM_PANGASIUS", "COM_SHRIMP"}:
        return "seafood"
    if order.commodity_id in {"COM_VEGETABLE", "COM_PURPLE_ONION"}:
        return "vegetable"
    if order.commodity_id in {"COM_RICE", "COM_SUGARCANE"}:
        return "grain_dry"
    return "hard_fruit"


def _vehicle_payload(vehicle: Vehicle, *, available_for_order: bool = True) -> dict[str, Any]:
    return {
        "vehicle_id": vehicle.license_plate,
        "mode": vehicle.mode,
        "capacity_kg": vehicle.capacity_kg,
        "capacity_ton": round(vehicle.capacity_kg / 1000.0, 1),
        "status": vehicle.status,
        "location": "CT_HUB" if vehicle.location == "can_tho" else vehicle.location,
        "current_lat": vehicle.current_lat,
        "current_lng": vehicle.current_lng,
        "available_for_order": available_for_order,
    }


def _parse_order_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _vehicles_needed(weight_kg: float, capacities_kg: list[float]) -> int:
    """Return the smallest number of prepared vehicles covering a load."""
    if weight_kg <= 0:
        return 0
    remaining = weight_kg
    count = 0
    for capacity in sorted((max(float(value), 0.0) for value in capacities_kg), reverse=True):
        if capacity <= 0:
            continue
        remaining -= capacity
        count += 1
        if remaining <= 0:
            return count
    return count


def _fleet_demand_forecast(session: Session, provider_id: int, forecast_date: date) -> dict[str, Any]:
    """Compare date-specific Can Tho demand with this provider's prepared fleet.

    Known orders are counted by their expected Can Tho arrival date.  A small
    rolling history supplies a transparent estimate for demand not yet booked;
    it is intentionally separate from Layer 2's inference model.
    """
    orders = session.exec(select(Order)).all()
    vehicles = session.exec(select(Vehicle).where(Vehicle.provider_id == provider_id)).all()
    modes: dict[str, dict[str, Any]] = {}
    for mode in ("road", "water"):
        daily_totals: defaultdict[date, float] = defaultdict(float)
        known_weight = 0.0
        order_count = 0
        for order in orders:
            if order.state in {"cancelled", "completed"} or order.selected_route_id not in {
                "B_ROAD_VIA_CT",
                "C_WATER_ROAD_VIA_CT",
                "D_WATER_VIA_CT",
                "E_ROAD_WATER_VIA_CT",
            }:
                continue
            order_mode = _outbound_mode(order)
            if order_mode != mode:
                continue
            order_date = _parse_order_date(order.eta_can_tho or order.timestamp or order.created_at)
            if order_date is None:
                continue
            weight = _weight(order)
            if order_date == forecast_date:
                known_weight += weight
                order_count += 1
            elif order_date < forecast_date:
                daily_totals[order_date] += weight

        historical_days = sorted(daily_totals)[-7:]
        historical_average = (
            sum(daily_totals[day] for day in historical_days) / len(historical_days)
            if historical_days else 0.0
        )
        # For a date that already has bookings, only a conservative 35% of the
        # recent average is added for late orders. For an empty future date,
        # the recent average is the forecast itself.
        predicted_unknown = historical_average * (0.35 if known_weight else 1.0)
        demand = known_weight + predicted_unknown

        mode_vehicles = [vehicle for vehicle in vehicles if vehicle.mode == mode]
        available = [
            vehicle for vehicle in mode_vehicles
            if vehicle.status == "available" and vehicle.location == "can_tho"
        ]
        prepared = [vehicle for vehicle in mode_vehicles if vehicle.status != "maintenance"]
        available_capacity = sum(vehicle.capacity_kg for vehicle in available)
        prepared_capacity = sum(vehicle.capacity_kg for vehicle in prepared)
        needed = _vehicles_needed(demand, [vehicle.capacity_kg for vehicle in prepared])
        confidence = min(0.95, 0.35 + 0.1 * len(historical_days)) if historical_days else 0.35
        modes[mode] = {
            "mode": mode,
            "demand_kg": round(demand, 1),
            "known_order_weight_kg": round(known_weight, 1),
            "predicted_weight_kg": round(predicted_unknown, 1),
            "orders_count": order_count,
            "vehicles_needed": needed,
            "available_vehicles": len(available),
            "prepared_vehicle_count": len(prepared),
            "available_capacity_kg": round(available_capacity, 1),
            "prepared_capacity_kg": round(prepared_capacity, 1),
            "enough_vehicles": available_capacity >= demand,
            "capacity_gap_kg": round(max(0.0, demand - available_capacity), 1),
            "confidence": round(confidence, 3),
        }

    return {
        "forecast_date": forecast_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "orders_and_provider_fleet",
        "scope": "network_demand_vs_provider_fleet",
        "modes": modes,
    }


async def _broadcast_state_update() -> None:
    from app.routes.websocket import ws_manager
    from app.state import state_manager

    state = await state_manager.get_state()
    await ws_manager.broadcast(state)


def _provider_order_response(session: Session, order: Order, provider_id: int, vehicles: list[Vehicle]) -> dict[str, Any]:
    options = [
        _vehicle_payload(vehicle)
        for vehicle in vehicles
        if vehicle.mode == _outbound_mode(order)
        and vehicle.status == "available"
        and vehicle.location == "can_tho"
        and vehicle.capacity_kg >= _weight(order)
    ]
    projection = order_projection(order, session, visibility_scope="provider_work_queue")
    projection.update(
        {
            "can_accept": (
                order.state == "arrived_waiting"
                and order.provider_assignment_status in {"unassigned", "assigned", "rejected"}
                and (order.assigned_provider_id in {None, provider_id})
            ),
            "required_outbound_mode": _outbound_mode(order),
            "transport_options": options,
        }
    )
    return projection


@router.get("/orders")
def get_logistics_order_queue(request: Request):
    """Return open Can Tho orders plus this provider's accepted/assigned orders."""

    user = _require_logistics(request)
    with Session(engine) as session:
        vehicles = session.exec(select(Vehicle).where(Vehicle.provider_id == user.id)).all()
        vehicle_by_plate = {vehicle.license_plate: vehicle for vehicle in vehicles}
        waiting_orders = session.exec(
            select(Order).where(Order.state == "arrived_waiting").order_by(Order.id.desc())
        ).all()
        visible = []
        for order in waiting_orders:
            is_open = order.assigned_provider_id is None and not order.assigned_vehicle_id
            is_mine = can_view_order(order, user, vehicle_by_plate)
            if is_open or is_mine:
                visible.append(_provider_order_response(session, order, user.id, vehicles))

        return {
            "orders": visible,
            "vehicles": [_vehicle_payload(vehicle) for vehicle in vehicles],
            "summary": {
                "open_orders": sum(1 for order in visible if order["provider_assignment_status"] in {"unassigned", "rejected"}),
                "accepted_orders": sum(1 for order in visible if order["provider_assignment_status"] == "accepted"),
                "waiting_weight_kg": round(sum(float(order["weight_ton"]) * 1000 for order in visible), 1),
            },
        }


@router.post("/orders/{order_id}/accept")
async def accept_logistics_order(order_id: int, payload: AcceptOrderPayload, request: Request):
    """Assign one waiting order to this provider and one of its vehicles."""

    user = _require_logistics(request)
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.state != "arrived_waiting":
            raise HTTPException(status_code=409, detail="Order is not waiting at Can Tho Hub")
        if order.assigned_provider_id not in {None, user.id}:
            raise HTTPException(status_code=409, detail="Order is already assigned to another provider")

        vehicle = session.get(Vehicle, payload.vehicle_id)
        if not vehicle or vehicle.provider_id != user.id:
            raise HTTPException(status_code=403, detail="Vehicle does not belong to this provider")
        if vehicle.status != "available" or vehicle.location != "can_tho":
            raise HTTPException(status_code=409, detail="Vehicle is not available at Can Tho Hub")
        if vehicle.mode != _outbound_mode(order):
            raise HTTPException(status_code=409, detail=f"Order requires a {_outbound_mode(order)} vehicle")
        if vehicle.capacity_kg < _weight(order):
            raise HTTPException(status_code=409, detail="Vehicle capacity is smaller than order weight")

        order.assigned_provider_id = user.id
        order.assigned_vehicle_id = vehicle.license_plate
        order.provider_assignment_status = "accepted"
        order.provider_assigned_at = now
        session.add(order)
        session.add(SystemLog(
            timestamp=now,
            event_type="PROVIDER_ORDER_ACCEPTED",
            message=f"Provider {user.email} accepted order #{order.id} with vehicle {vehicle.license_plate}.",
            payload_json=json.dumps({"order_id": order.id, "provider_id": user.id, "vehicle_id": vehicle.license_plate}),
        ))
        session.commit()
        session.refresh(order)
        response = order_projection(order, session, visibility_scope="provider_work_queue")

    await _broadcast_state_update()
    return {"status": "accepted", "order": response}


@router.post("/orders/dispatch")
async def dispatch_logistics_orders(payload: DispatchOrdersPayload, request: Request):
    """Dispatch a provider-selected batch on one compatible vehicle."""

    user = _require_logistics(request)
    order_ids = list(dict.fromkeys(payload.order_ids))
    if not order_ids:
        raise HTTPException(status_code=422, detail="At least one order is required")
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    with Session(engine) as session:
        vehicle = session.get(Vehicle, payload.vehicle_id)
        if not vehicle or vehicle.provider_id != user.id:
            raise HTTPException(status_code=403, detail="Vehicle does not belong to this provider")
        if vehicle.status != "available" or vehicle.location != "can_tho":
            raise HTTPException(status_code=409, detail="Vehicle is not available at Can Tho Hub")

        orders = [session.get(Order, order_id) for order_id in order_ids]
        if any(order is None for order in orders):
            raise HTTPException(status_code=404, detail="One or more orders were not found")
        typed_orders = [order for order in orders if order is not None]
        if any(order.state != "arrived_waiting" for order in typed_orders):
            raise HTTPException(status_code=409, detail="Every selected order must be waiting at Can Tho Hub")
        if any(order.assigned_provider_id != user.id or order.provider_assignment_status != "accepted" for order in typed_orders):
            raise HTTPException(status_code=409, detail="Every selected order must be accepted by this provider")
        if any(order.assigned_vehicle_id != vehicle.license_plate for order in typed_orders):
            raise HTTPException(status_code=409, detail="Select the vehicle used when accepting these orders")
        modes = {_outbound_mode(order) for order in typed_orders}
        if len(modes) != 1 or vehicle.mode not in modes:
            raise HTTPException(status_code=409, detail="Selected orders and vehicle must use the same transport mode")

        total_weight = sum(_weight(order) for order in typed_orders)
        if total_weight > vehicle.capacity_kg:
            raise HTTPException(status_code=409, detail="Selected orders exceed vehicle capacity")

        proposal_id = f"provider_{uuid.uuid4().hex}"
        vehicle_id = vehicle.license_plate
        eta_hcm = (now_dt + timedelta(hours=5)).isoformat()
        dispatch = DispatchOrder(
            proposal_id=proposal_id,
            vehicle_id=vehicle.license_plate,
            outbound_mode=vehicle.mode,
            destination="ho_chi_minh",
            shipment_ids_json=json.dumps([str(order.id) for order in typed_orders]),
            total_weight_kg=total_weight,
            capacity_kg=vehicle.capacity_kg,
            fill_ratio=min(total_weight / vehicle.capacity_kg, 1.0),
            status="waiting_for_pickup",
            created_at=now,
            dispatched_at=now,
            eta_hcm=eta_hcm,
        )
        session.add(dispatch)
        for order in typed_orders:
            order.state = "dispatched"
            order.dispatched_at = now
            order.dispatch_proposal_id = proposal_id
            order.provider_assignment_status = "dispatched"
            session.add(order)
            inventory = session.get(CargoInventory, _cargo_inventory_key(order))
            if inventory:
                inventory.volume = max(0.0, inventory.volume - _weight(order))
                session.add(inventory)
        vehicle.status = "in_transit"
        session.add(vehicle)
        session.add(SystemLog(
            timestamp=now,
            event_type="PROVIDER_DISPATCH_CREATED",
            message=f"Provider {user.email} dispatched {len(typed_orders)} order(s) via {vehicle.license_plate}.",
            payload_json=json.dumps({"proposal_id": proposal_id, "order_ids": order_ids, "vehicle_id": vehicle.license_plate}),
        ))
        session.commit()

    await _broadcast_state_update()
    return {
        "status": "dispatched",
        "proposal_id": proposal_id,
        "vehicle_id": vehicle_id,
        "order_ids": order_ids,
        "total_weight_kg": total_weight,
        "eta_hcm": eta_hcm,
    }

@router.get("/overview")
def get_logistics_overview(request: Request):
    user = current_user(request)
    if user is None or user.role != "logistics":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    provider_id = user.id

    with Session(engine) as session:
        # Get provider vehicles
        vehicles = session.exec(select(Vehicle).where(Vehicle.provider_id == provider_id)).all()
        vehicle_plates = [v.license_plate for v in vehicles]

        # Get dispatches for these vehicles
        dispatches = session.exec(
            select(DispatchOrder).where(DispatchOrder.vehicle_id.in_(vehicle_plates))
        ).all()

        active_deliveries_list = [d for d in dispatches if d.status != "completed"]

        # Parse delivery layers for the map
        delivery_layers = []
        for index, d in enumerate(active_deliveries_list):
            shipment_ids = json.loads(d.shipment_ids_json) if d.shipment_ids_json else []
            hub_id = "CT_HUB"
            route_code = "A_DIRECT_ROAD"
            if shipment_ids:
                order_id = int(shipment_ids[0]) if str(shipment_ids[0]).isdigit() else None
                if order_id:
                    order = session.get(Order, order_id)
                    if order:
                        hub_id = order.hub_id
                        route_code = order.selected_route_id or "A_DIRECT_ROAD"

            from app.services.map_data import route_options_for_hub
            segments = route_options_for_hub(hub_id)["routes"].get(route_code, [])

            delivery_layers.append({
                "delivery_id": f"JOB-{d.proposal_id}" if d.proposal_id else f"JOB-{d.id}",
                "route_code": route_code,
                "status": d.status,
                "eta": d.predicted_full_load_time or "N/A",
                "hub_id": hub_id,
                "segments": segments
            })

        # Parse waiting jobs for the map
        waiting_jobs = []
        waiting_dispatches = [d for d in dispatches if d.status == "waiting_for_pickup"]
        map_nodes = nodes()
        node_lookup = {node["node_id"]: node for node in map_nodes}

        for d in waiting_dispatches:
            shipment_ids = json.loads(d.shipment_ids_json) if d.shipment_ids_json else []
            hub_id = "CT_HUB"
            route_code = "A_DIRECT_ROAD"
            if shipment_ids:
                order_id = int(shipment_ids[0]) if str(shipment_ids[0]).isdigit() else None
                if order_id:
                    order = session.get(Order, order_id)
                    if order:
                        hub_id = order.hub_id
                        route_code = order.selected_route_id or "A_DIRECT_ROAD"

            node = node_lookup.get(hub_id)
            lat, lon = (node["lat"], node["lon"]) if node else (10.05, 105.75)

            waiting_jobs.append({
                "job_id": d.proposal_id,
                "hub_id": hub_id,
                "khoi_luong_tich_luy_hien_tai_kg": d.total_weight_kg,
                "quyet_dinh": "DISPATCH_NOW",
                "thoi_gian_de_xuat_chay": d.created_at,
                "route_code": route_code,
                "lat": lat,
                "lon": lon
            })

        # Fetch active orders from SQLite DB
        inbound_orders = session.exec(
            select(Order).where(Order.state.in_(["routed_to_can_tho", "arrived_waiting"]))
        ).all()
        
        from app.simulation import SYSTEM_CLOCK
        from datetime import datetime, timezone, timedelta
        from app.services.map_data import _point_along_segments

        # Build vehicle points
        vehicle_points = []
        for index, vehicle in enumerate(vehicles):
            status_val = vehicle.status
            veh_id = vehicle.license_plate
            
            # Check if vehicle has an active inbound order
            active_order = next((o for o in inbound_orders if o.assigned_vehicle_id == veh_id), None)
            
            # Check outbound active delivery
            active_d = next((d for d in active_deliveries_list if d.vehicle_id == veh_id), None)
            
            route_progress = None
            delivery_id = None
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

                    from app.services.map_data import route_options_for_hub
                    segments = route_options_for_hub(active_order.hub_id)["routes"].get(active_order.selected_route_id, [])
                    inbound_segs = [s for s in segments if s["to_node_id"] != "HCM_MARKET"]
                    if not inbound_segs:
                        inbound_segs = segments
                    lat, lon = _point_along_segments(inbound_segs, p)
                    status_val = "in_transit"
                    display_status = "in_delivery"
                    route_progress = p
                    delivery_id = f"ORDER-{active_order.id}"
                else: # arrived_waiting
                    # Snap to Can Tho Hub
                    lat, lon = 10.0452, 105.7469
                    status_val = "available"
                    display_status = "arrived_waiting"
                    delivery_id = f"ORDER-{active_order.id}"
            elif active_d and active_d.status != "completed":
                # Outbound dispatch tracking
                dl = next((layer for layer in delivery_layers if layer["delivery_id"] == f"JOB-{active_d.proposal_id}"), None)
                try:
                    start_time = datetime.fromisoformat(active_d.dispatched_at) if active_d.dispatched_at else datetime.now(timezone.utc)
                    end_time = datetime.fromisoformat(active_d.eta_hcm) if active_d.eta_hcm else start_time + timedelta(hours=5)
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)
                    total_sec = (end_time - start_time).total_seconds()
                    elapsed_sec = (SYSTEM_CLOCK - start_time).total_seconds()
                    p = max(0.0, min(1.0, elapsed_sec / total_sec if total_sec > 0 else 1.0))
                except:
                    p = 0.5
                    
                if dl and dl["segments"]:
                    outbound_segs = [s for s in dl["segments"] if s["to_node_id"] == "HCM_MARKET"]
                    if not outbound_segs:
                        outbound_segs = dl["segments"]
                    lat, lon = _point_along_segments(outbound_segs, p)
                else:
                    lat = vehicle.current_lat or 10.03
                    lon = vehicle.current_lng or 105.78
                display_status = "in_delivery"
                delivery_id = f"JOB-{active_d.proposal_id}"
                route_progress = p
            else:
                lat = vehicle.current_lat or 10.03
                lon = vehicle.current_lng or 105.78
                display_status = "available" if status_val == "available" else "unavailable"

            vehicle_points.append({
                "vehicle_id": vehicle.license_plate,
                "vehicle_type": vehicle.mode,
                "capacity_ton": str(vehicle.capacity_kg / 1000.0),
                "source_status": status_val,
                "display_status": display_status,
                "current_node_id": vehicle.location,
                "delivery_id": delivery_id,
                "route_progress": route_progress,
                "lat": lat,
                "lon": lon
            })

        counts = Counter(vp["display_status"] for vp in vehicle_points)
        summary = {
            "waiting_jobs": len(waiting_jobs),
            "active_deliveries": len(delivery_layers),
            "available_vehicles": counts["available"],
            "unavailable_vehicles": counts["unavailable"]
        }

        # Build local fleet grouped by node
        grouped = defaultdict(list)
        for vp in vehicle_points:
            grouped[vp["current_node_id"]].append(vp)
        fleet_list = []
        for node_id, rows in grouped.items():
            node = node_lookup.get(node_id)
            if not node:
                continue
            statuses = Counter(r["source_status"] for r in rows)
            fleet_list.append({
                "node_id": node_id,
                "lat": node["lat"],
                "lon": node["lon"],
                "count": len(rows),
                "statuses": dict(statuses),
                "vehicles": rows[:12]
            })

        map_payload = {
            "nodes": map_nodes,
            "legs": legs(),
            "fleet": fleet_list,
            "vehicle_points": vehicle_points,
            "waiting_jobs": waiting_jobs,
            "active_deliveries": delivery_layers,
            "summary": summary,
            "operational": True
        }

        return map_payload

@router.get("/fleet/forecast")
def get_logistics_fleet_forecast(
    request: Request,
    forecast_date: Optional[str] = Query(default=None),
):
    user = _require_logistics(request)
    target_date = date.today() + timedelta(days=1)
    if forecast_date:
        try:
            target_date = date.fromisoformat(forecast_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="forecast_date must use YYYY-MM-DD")
    with Session(engine) as session:
        return _fleet_demand_forecast(session, user.id, target_date)


@router.get("/fleet")
def get_logistics_fleet(request: Request, status_filter: Optional[str] = Query(default=None)):
    user = current_user(request)
    if user is None or user.role != "logistics":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    provider_id = user.id

    with Session(engine) as session:
        statement = select(Vehicle).where(Vehicle.provider_id == provider_id)
        if status_filter:
            statement = statement.where(Vehicle.status == status_filter)
        vehicles = session.exec(statement).all()

        return [
            {
                "vehicle_id": vehicle.license_plate,
                "mode": vehicle.mode,
                "vehicle_type": vehicle.mode,
                "capacity_ton": str(vehicle.capacity_kg / 1000.0),
                "status": vehicle.status,
                "current_node_id": "CT_HUB" if vehicle.location == "can_tho" else vehicle.location,
                "current_lat": vehicle.current_lat,
                "current_lng": vehicle.current_lng
            }
            for vehicle in vehicles
        ]

@router.get("/jobs")
def get_logistics_jobs(request: Request):
    user = current_user(request)
    if user is None or user.role != "logistics":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    provider_id = user.id

    with Session(engine) as session:
        vehicles = session.exec(select(Vehicle).where(Vehicle.provider_id == provider_id)).all()
        vehicle_plates = [v.license_plate for v in vehicles]

        dispatches = session.exec(
            select(DispatchOrder).where(DispatchOrder.vehicle_id.in_(vehicle_plates))
        ).all()

        jobs_list = []
        for d in dispatches:
            shipment_ids = json.loads(d.shipment_ids_json) if d.shipment_ids_json else []
            shipments = []
            hub_id = "CT_HUB"
            route_code = "A_DIRECT_ROAD"

            for s_id in shipment_ids:
                order_id = int(s_id) if str(s_id).isdigit() else None
                if order_id:
                    order = session.get(Order, order_id)
                    if order:
                        hub_id = order.hub_id
                        route_code = order.selected_route_id or "A_DIRECT_ROAD"
                        shipments.append({
                            "shipment_id": order.id,
                            "hub_id": order.hub_id,
                            "commodity_id": order.commodity_id or "N/A",
                            "loai_hang": order.loai_hang or "N/A",
                            "weight_kg": order.khoi_luong_kg,
                            "deadline": order.deadline_ts or order.delivery_deadline or "N/A",
                            "business_name": order_projection(order, session, visibility_scope="provider_job").get("business_name"),
                            "state_code": order.state,
                        })

            jobs_list.append({
                "job_id": d.proposal_id,
                "vehicle_plate": d.vehicle_id,
                "mode": d.outbound_mode,
                "total_weight_kg": d.total_weight_kg,
                "capacity_kg": d.capacity_kg,
                "fill_ratio": d.fill_ratio,
                "status": d.status,
                "created_at": d.created_at,
                "hub_id": hub_id,
                "route_code": route_code,
                "shipments": shipments
            })

        return jobs_list
