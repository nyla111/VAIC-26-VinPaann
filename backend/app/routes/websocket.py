import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from app.models import SystemState, Order, SystemLog
from app.state import state_manager
from app.database import engine
from app.ai.route_optimizer.optimizer import optimize_route

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

    async def broadcast(self, state: SystemState):
        """
        Sends the SystemState JSON payload to all connected clients.
        """
        if not self.active_connections:
            return
            
        payload = state.model_dump_json()
        
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error broadcasting state to client: {e}")
                disconnected_clients.append(connection)

        for client in disconnected_clients:
            self.disconnect(client)


# Global WebSocket connection manager instance
ws_manager = ConnectionManager()


async def stream_cargo_tracking(websocket: WebSocket, order_id: int):
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

                origin = HUB_COORDS.get(order.hub_id, (10.0, 105.0))
                ct = HUB_COORDS["CT_HUB"]
                hcm = HUB_COORDS["HCM_MARKET"]
                
                state = order.state
                lat, lon = origin
                progress = 0.0
                
                if state == "created":
                    lat, lon = origin
                    progress = 0.0
                elif state in ["routed_to_can_tho", "in_transit_to_can_tho"]:
                    try:
                        dt = datetime.fromisoformat(order.timestamp)
                    except:
                        dt = datetime.now(timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    progress = min(elapsed / 3.0, 1.0)
                    lat = origin[0] + (ct[0] - origin[0]) * progress
                    lon = origin[1] + (ct[1] - origin[1]) * progress
                elif state == "arrived_waiting":
                    lat, lon = ct
                    progress = 1.0
                elif state == "dispatched":
                    start_point = origin if order.selected_route_id == "A_DIRECT_ROAD" else ct
                    if order.dispatched_at:
                        try:
                            dt = datetime.fromisoformat(order.dispatched_at)
                        except:
                            dt = datetime.now(timezone.utc)
                    else:
                        try:
                            dt = datetime.fromisoformat(order.actual_arrival_at) if order.actual_arrival_at else datetime.now(timezone.utc)
                        except:
                            dt = datetime.now(timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    progress = min(elapsed / 5.0, 1.0)
                    lat = start_point[0] + (hcm[0] - start_point[0]) * progress
                    lon = start_point[1] + (hcm[1] - start_point[1]) * progress
                else:
                    lat, lon = hcm
                    progress = 1.0
                
                await websocket.send_json({
                    "event": "CARGO_TRACKING",
                    "order_id": order_id,
                    "state": state,
                    "location": {"lat": lat, "lon": lon},
                    "progress": progress
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
    await websocket.accept()
    tracking_task = None
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "CREATE_ORDER":
                hub_id = data.get("hub_id")
                loai_hang = data.get("loai_hang", "")
                commodity_id = resolve_commodity_id(loai_hang)
                khoi_luong_kg = float(data.get("khoi_luong_kg", 0.0))
                timestamp = data.get("timestamp")
                delivery_deadline = data.get("delivery_deadline")
                harvested_at = data.get("harvested_at")
                user_id = data.get("user_id")


                with Session(engine) as session:
                    db_order = Order(
                        hub_id=hub_id,
                        commodity_id=commodity_id,
                        loai_hang=loai_hang,
                        khoi_luong_kg=khoi_luong_kg,
                        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        state="created",
                        delivery_deadline=delivery_deadline,
                        harvested_at=harvested_at,
                        user_id=int(user_id) if user_id else None
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
                    if order:
                        order.selected_route_id = selected_route_id
                        if selected_route_id == "A_DIRECT_ROAD":
                            order.state = "dispatched"
                            order.dispatched_at = now_str
                            log_msg = f"Direct Route: Shipment #{order_id} ({order.khoi_luong_kg:.1f} kg) dispatched directly to HCM bypassing Can Tho."
                        else:
                            order.state = "routed_to_can_tho"
                            order.timestamp = now_str
                            log_msg = f"Route Selected: Shipment #{order_id} ({order.khoi_luong_kg:.1f} kg) routed via Can Tho. In transit to Can Tho..."
                        
                        session.add(order)
                        session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                        session.commit()
                        state_val = order.state
                    else:
                        state_val = "error"

                # Broadcast system state
                updated_state = await state_manager.get_state()
                await ws_manager.broadcast(updated_state)

                await websocket.send_json({
                    "event": "ROUTE_CONFIRMED",
                    "order_id": order_id,
                    "state": state_val
                })

                if selected_route_id != "A_DIRECT_ROAD" and state_val == "routed_to_can_tho":
                    # Trigger simulation in background
                    from app.routes.hub import simulate_shipment_arrival
                    asyncio.create_task(simulate_shipment_arrival(order_id))

            elif action == "TRACK_CARGO":
                order_id = int(data.get("order_id"))
                if tracking_task:
                    tracking_task.cancel()
                tracking_task = asyncio.create_task(stream_cargo_tracking(websocket, order_id))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from action endpoint.")
    except Exception as e:
        logger.error(f"WebSocket action handler error: {e}")
    finally:
        if tracking_task:
            tracking_task.cancel()


@router.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Sends current state immediately upon connection, then maintains a keep-alive listener.
    """
    await ws_manager.connect(websocket)
    
    try:
        current_state = await state_manager.get_state()
        await websocket.send_text(current_state.model_dump_json())
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
