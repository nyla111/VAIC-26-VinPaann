import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from app.models import SystemState, Order, SystemLog, User, Vehicle
from app.state import state_manager
from app.database import engine
from app.ai.route_optimizer.optimizer import optimize_route
from app.order_times import effective_harvested_at
from app.services.order_lifecycle import create_direct_dispatch
from app.services.order_views import can_view_order

logger = logging.getLogger(__name__)
router = APIRouter()


def resolve_commodity_id(loai_hang: str) -> str | None:
    from app.ai.normalizers import normalize_text
    text = normalize_text(loai_hang or "")
    mapping = {
        "gao": "COM_RICE",
        "lua": "COM_RICE",
        "rice": "COM_RICE",
        "ca tra": "COM_PANGASIUS",
        "ca_tra": "COM_PANGASIUS",
        "pangasius": "COM_PANGASIUS",
        "tom": "COM_SHRIMP",
        "tôm": "COM_SHRIMP",
        "shrimp": "COM_SHRIMP",
        "buoi": "COM_POMELO",
        "bưởi": "COM_POMELO",
        "pomelo": "COM_POMELO",
        "hanh tim": "COM_PURPLE_ONION",
        "hành tím": "COM_PURPLE_ONION",
        "purple onion": "COM_PURPLE_ONION",
        "khoai lang": "COM_SWEET_POTATO",
        "khoai_lang": "COM_SWEET_POTATO",
        "rau": "COM_VEGETABLE",
        "vegetable": "COM_VEGETABLE",
        "mia": "COM_SUGARCANE",
        "mía": "COM_SUGARCANE",
        "sugarcane": "COM_SUGARCANE",
        "khom": "COM_PINEAPPLE",
        "dua": "COM_PINEAPPLE",
        "dứa": "COM_PINEAPPLE",
        "pineapple": "COM_PINEAPPLE",
        "cam": "COM_ORANGE",
        "orange": "COM_ORANGE"
    }
    for kw, cid in mapping.items():
        if kw in text:
            return cid
    return None



class ConnectionManager:
    """
    Manages active client WebSocket connections for real-time state streaming.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_event(self, event: str, data: Any):
        """Broadcast a versionable event to every dashboard connection."""
        if not self.active_connections:
            return

        if isinstance(data, SystemState):
            state_data = data.model_dump(mode="json")
            payload_obj = {"event": event, "data": state_data, **state_data}
        else:
            payload_obj = {"event": event, "data": data}
        payload = json.dumps(payload_obj, ensure_ascii=False)
        
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error broadcasting state to client: {e}")
                disconnected_clients.append(connection)

        for client in disconnected_clients:
            self.disconnect(client)

    async def broadcast(self, state: SystemState):
        await self.broadcast_event("STATE_UPDATE", state)


# Global WebSocket connection manager instance
ws_manager = ConnectionManager()


def websocket_user(websocket: WebSocket) -> dict[str, Any] | None:
    """Resolve the signed SessionMiddleware identity for a WebSocket.

    The browser may include a user id in an old client payload, but that value
    is never trusted.  Cookies/session data are the authority for this
    endpoint, just as they are for the HTTP APIs.
    """

    session_data = websocket.scope.get("session") or {}
    user_id = session_data.get("user_id")
    role = session_data.get("role")
    if not user_id or not role:
        return None
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user or user.role != role:
            return None
        return {"id": user.id, "role": user.role, "email": user.email}


async def send_websocket_auth_error(websocket: WebSocket, message: str = "Authentication required") -> None:
    await websocket.send_json({"event": "ERROR", "code": "UNAUTHORIZED", "message": message})


def order_visible_to_websocket_user(order: Order, viewer: dict[str, Any]) -> bool:
    with Session(engine) as session:
        vehicles = {
            vehicle.license_plate: vehicle
            for vehicle in session.exec(select(Vehicle)).all()
        }
        return can_view_order(order, viewer, vehicles)


async def stream_cargo_tracking(websocket: WebSocket, order_id: int, viewer: dict[str, Any]):
    """
    Continuously queries the order state and interpolates real-time location.
    Streams geolocation markers back to the client every 1 second.
    """
    HUB_COORDS = {
        "HUB_VITHANH": (9.784, 105.4701),
        "HUB_LONGXUYEN": (10.3864, 105.4352),
        "HUB_SOCTRANG": (9.6025, 105.9739),
        "HUB_VINHLONG": (10.2537, 105.9722),
        "CT_HUB": (10.0452, 105.7469),
        "HCM_MARKET": (10.7769, 106.7009)
    }

    try:
        while True:
            with Session(engine) as session:
                order = session.get(Order, order_id)
                if not order:
                    await websocket.send_json({"event": "CARGO_TRACKING_ERROR", "message": f"Order #{order_id} not found."})
                    break
                vehicles = {
                    vehicle.license_plate: vehicle
                    for vehicle in session.exec(select(Vehicle)).all()
                }
                if not can_view_order(order, viewer, vehicles):
                    await websocket.send_json({
                        "event": "CARGO_TRACKING_ERROR",
                        "message": "You do not have access to this order.",
                    })
                    break

                origin = HUB_COORDS.get(order.hub_id, (10.0, 105.0))
                ct = HUB_COORDS["CT_HUB"]
                hcm = HUB_COORDS["HCM_MARKET"]
                
                from app.simulation import SYSTEM_CLOCK
                from datetime import datetime, timezone
                from app.services.map_data import route_options_for_hub, _point_along_segments
                
                route_code = order.selected_route_id or "B_ROAD_VIA_CT"
                route_data = route_options_for_hub(order.hub_id)
                segments = route_data.get("routes", {}).get(route_code, [])
                
                state = order.state
                
                from app.mappings import enrich_order_payload
                enriched = enrich_order_payload(order, session)
                progress = enriched["progress"] / 100.0
                lat, lon = origin
                
                if state == "created":
                    lat, lon = origin
                elif state in ["routed_to_can_tho", "in_transit_to_can_tho"]:
                    inbound_segs = [s for s in segments if s["to_node_id"] != "HCM_MARKET"]
                    if not inbound_segs:
                        inbound_segs = segments
                    lat, lon = _point_along_segments(inbound_segs, progress)
                elif state == "arrived_waiting":
                    lat, lon = ct
                elif state == "dispatched":
                    outbound_segs = [s for s in segments if s["to_node_id"] == "HCM_MARKET"]
                    if not outbound_segs:
                        outbound_segs = segments
                    lat, lon = _point_along_segments(outbound_segs, progress)
                else:
                    lat, lon = hcm
                
                await websocket.send_json({
                    "event": "CARGO_TRACKING",
                    "order_id": order_id,
                    "state": state,
                    "location": {"lat": lat, "lon": lon},
                    "progress": progress,
                    "provider_name": enriched.get("provider_name"),
                    "timeline": enriched.get("timeline")
                })
                
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in stream_cargo_tracking: {e}")


@router.websocket("/ws")
async def websocket_client_endpoint(websocket: WebSocket):
    """
    Unified client action WebSocket endpoint for submit-to-track workflow.
    """
    await ws_manager.connect(websocket)
    tracking_task = None
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            viewer = websocket_user(websocket)

            if viewer is None:
                await send_websocket_auth_error(websocket)
                continue
            
            if action == "CREATE_ORDER":
                if viewer["role"] != "enterprise":
                    await send_websocket_auth_error(websocket, "Only enterprise users can create orders.")
                    continue
                hub_id = data.get("hub_id")
                loai_hang = data.get("loai_hang", "")
                commodity_id = resolve_commodity_id(loai_hang)
                khoi_luong_kg = float(data.get("khoi_luong_kg", 0.0))
                timestamp = data.get("timestamp")
                delivery_deadline = data.get("delivery_deadline")
                harvested_at = data.get("harvested_at")
                created_at = datetime.now(timezone.utc).isoformat()
                harvested_at = effective_harvested_at(harvested_at, created_at)


                with Session(engine) as session:
                    db_order = Order(
                        hub_id=hub_id,
                        commodity_id=commodity_id,
                        loai_hang=loai_hang,
                        khoi_luong_kg=khoi_luong_kg,
                        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                        created_at=created_at,
                        state="created",
                        delivery_deadline=delivery_deadline,
                        harvested_at=harvested_at,
                        user_id=viewer["id"]
                    )
                    session.add(db_order)
                    session.commit()
                    session.refresh(db_order)
                    order_id = db_order.id
                
                input_data = {
                    "order_id": str(order_id),
                    "hub_id": hub_id,
                    "commodity_id": commodity_id,
                    "loai_hang": loai_hang,
                    "khoi_luong_kg": khoi_luong_kg,
                    "timestamp": timestamp,
                    "deadline_ts": delivery_deadline
                }
                
                result = optimize_route(input_data)
                from app.services.map_data import route_options_for_hub
                route_map = route_options_for_hub(hub_id)

                # Attach the complete Layer 1 snapshot to the same SQLite
                # order that Layer 2 will later query.
                with Session(engine) as session:
                    persisted_order = session.get(Order, order_id)
                    if persisted_order:
                        persisted_order.route_options_json = json.dumps(result.get("phuong_an", []), ensure_ascii=False)
                        persisted_order.selected_route_geometry_json = json.dumps(
                            route_map.get("routes", {}), ensure_ascii=False
                        )
                        persisted_order.optimizer_version = "route_optimizer_v1"
                        session.add(persisted_order)
                        session.commit()

                await websocket.send_json({
                    "event": "ROUTE_OPTIONS",
                    "data": result,
                    "route_map": route_map,
                    "order_id": order_id
                })

            elif action == "CONFIRM_ROUTE":
                order_id = int(data.get("order_id"))
                selected_route_id = data.get("selected_route_id")
                
                timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                now_str = datetime.now(timezone.utc).isoformat()

                with Session(engine) as session:
                    order = session.get(Order, order_id)
                    if order and order_visible_to_websocket_user(order, viewer):
                        if not order.harvested_at:
                            order.harvested_at = order.created_at
                        available_routes = {
                            option.get("route_code")
                            for option in (json.loads(order.route_options_json) if order.route_options_json else [])
                        }
                        if available_routes and selected_route_id not in available_routes:
                            await websocket.send_json({
                                "event": "ERROR",
                                "code": "ROUTE_NOT_IN_OPTIONS",
                                "message": "Selected route was not returned by Layer 1.",
                            })
                            continue
                        order.selected_route_id = selected_route_id
                        selected_option = next(
                            (option for option in (json.loads(order.route_options_json) if order.route_options_json else [])
                             if option.get("route_code") == selected_route_id),
                            None,
                        )
                        if selected_option:
                            order.selected_route_cost_vnd = selected_option.get("chi_phi_du_doan_vnd")
                            order.selected_route_eta_hours = selected_option.get("thoi_gian_du_kien_gio")
                        if selected_route_id == "A_DIRECT_ROAD":
                            order.state = "dispatched"
                            order.dispatched_at = now_str
                            create_direct_dispatch(session, order, datetime.now(timezone.utc))
                            log_msg = f"Direct Route: Shipment #{order_id} ({order.khoi_luong_kg:.1f} kg) dispatched directly to HCM bypassing Can Tho."
                        else:
                            order.state = "routed_to_can_tho"
                            order.timestamp = now_str
                            
                            from app.simulation import SYSTEM_CLOCK
                            from datetime import timedelta
                            from app.models import Vehicle
                            
                            inbound_mode = "water" if selected_route_id in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else "road"
                            veh = session.exec(select(Vehicle).where(Vehicle.mode == inbound_mode, Vehicle.status == "available")).first()
                            
                            if veh:
                                order.assigned_vehicle_id = veh.license_plate
                                order.assigned_provider_id = veh.provider_id
                                order.provider_assignment_status = "assigned"
                                order.provider_assigned_at = now_str
                                veh.status = "en_route"
                                veh.location = order.hub_id
                                session.add(veh)
                            
                            eta_hours = order.selected_route_eta_hours or 2.0
                            order.eta_can_tho = (SYSTEM_CLOCK + timedelta(hours=eta_hours)).isoformat()
                            
                            log_msg = f"Route Selected: Shipment #{order_id} ({order.khoi_luong_kg:.1f} kg) routed via Can Tho. In transit via vehicle {veh.license_plate if veh else 'None'}..."
                        
                        session.add(order)
                        session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                        session.commit()
                        state_val = order.state
                    else:
                        await websocket.send_json({
                            "event": "ERROR",
                            "code": "ORDER_NOT_FOUND",
                            "message": "Order not found or not accessible.",
                        })
                        continue

                # Broadcast system state
                updated_state = await state_manager.get_state()
                await ws_manager.broadcast(updated_state)

                await websocket.send_json({
                    "event": "ROUTE_CONFIRMED",
                    "order_id": order_id,
                    "state": state_val
                })

            elif action == "TRACK_CARGO":
                order_id = int(data.get("order_id"))
                with Session(engine) as session:
                    order = session.get(Order, order_id)
                    if not order or not order_visible_to_websocket_user(order, viewer):
                        await websocket.send_json({
                            "event": "CARGO_TRACKING_ERROR",
                            "message": "Order not found or not accessible.",
                        })
                        continue
                if tracking_task:
                    tracking_task.cancel()
                tracking_task = asyncio.create_task(stream_cargo_tracking(websocket, order_id, viewer))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from action endpoint.")
    except Exception as e:
        logger.error(f"WebSocket action handler error: {e}")
    finally:
        if tracking_task:
            tracking_task.cancel()
        ws_manager.disconnect(websocket)


@router.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Sends current state immediately upon connection, then maintains a keep-alive listener.
    """
    await ws_manager.connect(websocket)
    
    try:
        current_state = await state_manager.get_state()
        state_data = current_state.model_dump(mode="json")
        await websocket.send_json({"event": "STATE_UPDATE", "data": state_data, **state_data})
    except Exception as e:
        logger.error(f"Failed to send initial state to socket: {e}")
        ws_manager.disconnect(websocket)
        return

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        ws_manager.disconnect(websocket)
