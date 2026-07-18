import random
from datetime import datetime
import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.config import CARGO_TYPES, HUBS, WEATHER_CONDITIONS
from app.models import RouteSelectRequest, SystemState
from app.state import state_manager
from sqlmodel import Session
from datetime import timezone
from app.models import RouteSelectRequest, SystemState, Order, CargoInventory, SystemLog
from app.state import state_manager
from app.routes.websocket import ws_manager
from app.ai.route_optimizer.optimizer import optimize_route
from app.database import engine

router = APIRouter()

async def simulate_shipment_arrival(order_id: int):
    """
    Background worker task:
    Simulates shipment transportation from a local hub to Can Tho (3 seconds for demo).
    Updates state to arrived_waiting, logs arrival, and triggers Layer 2 evaluation.
    """
    # 1. Simulate travel time
    await anyio.sleep(3.0)
    
    actual_arrival = datetime.now(timezone.utc).isoformat()
    timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with Session(engine) as session:
        order = session.get(Order, order_id)
        if order:
            # 2. Update order status in SQLite DB
            order.state = "arrived_waiting"
            order.actual_arrival_at = actual_arrival
            order.actual_weight_kg = order.khoi_luong_kg
            session.add(order)
            
            # Log arrival details
            log_msg = f"Hub Incoming: Shipment #{order_id} ({order.khoi_luong_kg:.1f} kg of {order.commodity_id or order.loai_hang}) arrived at Can Tho Hub from {order.hub_id}."
            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
            
            # 3. Accumulate volume in CargoInventory (compatible with old dashboard charts)
            from app.ai.normalizers import classify_priority
            priority = classify_priority(order.commodity_id, order.loai_hang)
            cargo_type = priority["tier"]
            
            inv = session.get(CargoInventory, cargo_type)
            if not inv:
                inv = CargoInventory(cargo_type=cargo_type, volume=0.0)
                session.add(inv)
            inv.volume += order.khoi_luong_kg
            
            session.commit()
            
            # 4. Trigger Layer 2 Decision Engine
            await state_manager.evaluate_and_dispatch()

    # 5. Broadcast updated system state to client dashboards
    updated_state = await state_manager.get_state()
    await ws_manager.broadcast(updated_state)


@router.post("/select-route", response_model=SystemState, status_code=status.HTTP_200_OK)
async def select_route(request: RouteSelectRequest, background_tasks: BackgroundTasks):
    """
    Registers route choice for shipments. If routing through Can Tho, initiates background transport simulation.
    """
    # Validation
    if request.hub_id not in HUBS:
        raise HTTPException(status_code=400, detail=f"Invalid hub_id. Supported: {HUBS}")
    if request.cargo_type not in CARGO_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid cargo_type. Supported: {CARGO_TYPES}")
    if request.volume <= 0.0:
        raise HTTPException(status_code=400, detail="Volume must be positive.")
    if request.weather not in WEATHER_CONDITIONS:
        raise HTTPException(status_code=400, detail=f"Invalid weather. Supported: {WEATHER_CONDITIONS}")

    # 1. Update weather setting and broadcast intermediate state
    state = await state_manager.set_weather(request.weather)
    
    target_order_id = None
    timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Process route selection
    if request.selected_route_id in ["B_ROAD_VIA_CT", "C_WATER_ROAD_VIA_CT", "D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"]:
        # Update or create Order in SQLite
        with Session(engine) as session:
            db_order = None
            if request.order_id:
                try:
                    db_order = session.get(Order, int(request.order_id))
                except:
                    pass
            
            if db_order:
                db_order.selected_route_id = request.selected_route_id
                db_order.state = "routed_to_can_tho"
            else:
                db_order = Order(
                    hub_id=request.hub_id,
                    commodity_id=None,
                    loai_hang=request.cargo_type,
                    khoi_luong_kg=request.volume,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    selected_route_id=request.selected_route_id,
                    state="routed_to_can_tho"
                )
            session.add(db_order)
            session.commit()
            session.refresh(db_order)
            target_order_id = db_order.id
            
            # Ghi log chọn tuyến Cần Thơ
            log_msg = f"Route Selected: Shipment #{target_order_id} ({request.volume:.1f} kg of {request.cargo_type}) from {request.hub_id} routed via Can Tho. Dispatching to Can Tho..."
            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
            session.commit()
            
        state = await state_manager.get_state()
        await ws_manager.broadcast(state)
        
        # Start the background task to simulate travel & arrival
        background_tasks.add_task(simulate_shipment_arrival, target_order_id)
        
    else:
        # Direct shipment bypassing Can Tho (A_DIRECT_ROAD)
        with Session(engine) as session:
            db_order = None
            if request.order_id:
                try:
                    db_order = session.get(Order, int(request.order_id))
                except:
                    pass
            if db_order:
                db_order.selected_route_id = request.selected_route_id
                db_order.state = "dispatched"
                session.add(db_order)
            else:
                db_order = Order(
                    hub_id=request.hub_id,
                    commodity_id=None,
                    loai_hang=request.cargo_type,
                    khoi_luong_kg=request.volume,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    selected_route_id=request.selected_route_id,
                    state="dispatched"
                )
                session.add(db_order)
                
            log_msg = f"Direct Route: {request.volume:.2f} kg of {request.cargo_type} from {request.hub_id} dispatched directly to HCM."
            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
            session.commit()
            
        state = await state_manager.get_state()
        await ws_manager.broadcast(state)

    return state



@router.get("/status", response_model=SystemState)
async def get_cantho_status():
    """
    Pull-based state synchronization fallback for dashboard UI.
    """
    return await state_manager.get_state()


@router.post("/simulate-incoming", status_code=status.HTTP_202_ACCEPTED)
async def simulate_incoming(background_tasks: BackgroundTasks):
    """
    Simulation utility for hackathon judges and testing:
    Generates a randomized local shipment event, optimizes route,
    selects recommended path, and runs the entire pipeline end-to-end.
    """
    # Pick a random hub (excluding Can Tho to simulate provincial inbound cargo)
    provincial_hubs = [h for h in HUBS if h != "CT_HUB"]
    hub = random.choice(provincial_hubs)
    cargo = random.choice(CARGO_TYPES)
    
    # Simulate volume in kg (e.g. 5,000 to 25,000 kg)
    volume = round(random.uniform(5000.0, 25000.0), 2)
    weather = random.choice(WEATHER_CONDITIONS)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+07:00")

    # 1. Call Layer 1 Optimizer to get recommended route
    try:
        result = optimize_route({
            "hub_id": hub,
            "commodity_id": None,
            "loai_hang": cargo,
            "khoi_luong_kg": volume,
            "timestamp": timestamp
        })
        recommended_route = result["recommended_route"]
        khuyen_nghi_ten = result["khuyen_nghi"]
    except Exception as e:
        # Fallback in case of optimization error during simulation
        recommended_route = "A_DIRECT_ROAD"
        khuyen_nghi_ten = "di_thang_hcm"

    # 2. Structure RouteSelectRequest payload
    select_payload = RouteSelectRequest(
        hub_id=hub,
        selected_route_id=recommended_route or "A_DIRECT_ROAD",
        cargo_type=cargo,
        volume=volume,
        weather=weather
    )

    # 3. Register route selection and add to background task
    state = await select_route(select_payload, background_tasks)

    return {
        "message": f"Simulation Event Triggered: Inbound cargo from {hub}.",
        "cargo_details": {
            "origin": hub,
            "cargo_type": cargo,
            "volume_kg": volume,
            "weather": weather
        },
        "optimized_decision": {
            "route_id": recommended_route,
            "route_name": khuyen_nghi_ten,
            "recommendation_reason": "Recommended by Layer 1 actual Optimizer model"
        },
        "current_system_state": state
    }

