import random
from datetime import datetime
import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from app.config import CARGO_TYPES, HUBS, WEATHER_CONDITIONS
from app.models import RouteSelectRequest, SystemState
from app.state import state_manager
from sqlmodel import Session, select
from datetime import timezone
from app.models import RouteSelectRequest, SystemState, Order, CargoInventory, SystemLog, Vehicle
from app.state import state_manager
from app.routes.websocket import ws_manager
from app.ai.route_optimizer.optimizer import optimize_route
from app.database import engine
from app.order_times import effective_harvested_at
from app.services.order_lifecycle import create_direct_dispatch
from app.routes.auth import current_user

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
            if not order.harvested_at:
                order.harvested_at = effective_harvested_at(None, order.created_at)
            session.add(order)

            if order.assigned_vehicle_id:
                inbound_vehicle = session.get(Vehicle, order.assigned_vehicle_id)
                if inbound_vehicle:
                    inbound_vehicle.status = "available"
                    inbound_vehicle.location = "can_tho"
                    session.add(inbound_vehicle)
            
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
async def select_route(
    request: RouteSelectRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
):
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
    viewer = current_user(http_request) if http_request is not None else None

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
                if viewer is None or (
                    viewer.role != "admin" and db_order.user_id != viewer.id
                ):
                    raise HTTPException(status_code=403, detail="Order is not accessible")
                db_order.selected_route_id = request.selected_route_id
                db_order.state = "routed_to_can_tho"
            else:
                created_at = datetime.now(timezone.utc).isoformat()
                db_order = Order(
                    hub_id=request.hub_id,
                    commodity_id=None,
                    loai_hang=request.cargo_type,
                    khoi_luong_kg=request.volume,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    created_at=created_at,
                    harvested_at=effective_harvested_at(None, created_at),
                    selected_route_id=request.selected_route_id,
                    state="routed_to_can_tho",
                    user_id=viewer.id if viewer and viewer.role == "enterprise" else None,
                )
                db_order.harvested_at = effective_harvested_at(None, db_order.created_at)
                
            from app.simulation import SYSTEM_CLOCK
            from datetime import timedelta
            from app.models import Vehicle
            
            inbound_mode = "water" if request.selected_route_id in ["D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"] else "road"
            veh = session.exec(select(Vehicle).where(Vehicle.mode == inbound_mode, Vehicle.status == "available")).first()
            
            if veh:
                db_order.assigned_vehicle_id = veh.license_plate
                db_order.assigned_provider_id = veh.provider_id
                db_order.provider_assignment_status = "assigned"
                db_order.provider_assigned_at = datetime.now(timezone.utc).isoformat()
                veh.status = "en_route"
                veh.location = db_order.hub_id
                session.add(veh)
            
            eta_hours = db_order.selected_route_eta_hours or 2.0
            db_order.eta_can_tho = (SYSTEM_CLOCK + timedelta(hours=eta_hours)).isoformat()
            
            session.add(db_order)
            session.commit()
            session.refresh(db_order)
            target_order_id = db_order.id
            
            # Ghi log chọn tuyến Cần Thơ
            log_msg = f"Route Selected: Shipment #{target_order_id} ({request.volume:.1f} kg of {request.cargo_type}) from {request.hub_id} routed via Can Tho. In transit via vehicle {veh.license_plate if veh else 'None'}..."
            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
            session.commit()
            
        state = await state_manager.get_state()
        await ws_manager.broadcast(state)
        # Background arrival simulation task is removed as the simulation loop will handle it based on system clock.
        
    else:
        # Direct shipment bypassing Can Tho (A_DIRECT_ROAD)
        with Session(engine) as session:
            db_order = None
            if request.order_id:
                try:
                    db_order = session.get(Order, int(request.order_id))
                except:
                    pass
            now_str = datetime.now(timezone.utc).isoformat()
            if db_order:
                if viewer is None or (
                    viewer.role != "admin" and db_order.user_id != viewer.id
                ):
                    raise HTTPException(status_code=403, detail="Order is not accessible")
                db_order.selected_route_id = request.selected_route_id
                db_order.state = "dispatched"
                db_order.dispatched_at = now_str
                create_direct_dispatch(session, db_order, datetime.now(timezone.utc))
                session.add(db_order)
            else:
                created_at = datetime.now(timezone.utc).isoformat()
                db_order = Order(
                    hub_id=request.hub_id,
                    commodity_id=None,
                    loai_hang=request.cargo_type,
                    khoi_luong_kg=request.volume,
                    timestamp=now_str,
                    created_at=created_at,
                    harvested_at=effective_harvested_at(None, created_at),
                    selected_route_id=request.selected_route_id,
                    state="dispatched",
                    dispatched_at=now_str,
                    user_id=viewer.id if viewer and viewer.role == "enterprise" else None,
                )
                session.add(db_order)
                session.flush()
                create_direct_dispatch(session, db_order, datetime.now(timezone.utc))

                
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
    state = await select_route(select_payload, background_tasks, None)

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
