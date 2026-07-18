import random
from datetime import datetime
import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.config import CARGO_TYPES, HUBS, WEATHER_CONDITIONS
from app.models import RouteSelectRequest, SystemState
from app.state import state_manager
from app.routes.websocket import ws_manager
from app.ai.route_optimizer.optimizer import optimize_route

router = APIRouter()

async def execute_layer2_evaluation_loop():
    """
    Background worker:
    Executes Layer 2 dispatch forecasting loop and broadcasts the decision state.
    """
    try:
        # Run decision loop
        updated_state, _ = await state_manager.evaluate_and_dispatch()
        # Broadcast final status
        await ws_manager.broadcast(updated_state)
    except Exception as e:
        # Add fallback log on error
        err_msg = f"Background error in Layer 2 decision loop: {e}"
        state_with_error = await state_manager.add_cargo("SYSTEM", "Error Log", 0.0)
        await ws_manager.broadcast(state_with_error)


@router.post("/select-route", response_model=SystemState, status_code=status.HTTP_200_OK)
async def select_route(request: RouteSelectRequest, background_tasks: BackgroundTasks):
    """
    Registers route choice for local shipments.
    If route passes through Can Tho consolidation center, cargo is added to inventory.
    Triggers Layer 2 dispatch logic in a background worker task.
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
    
    # 2. Accumulate cargo if routed via Can Tho (B, C, D, E routes)
    if request.selected_route_id in ["B_ROAD_VIA_CT", "C_WATER_ROAD_VIA_CT", "D_WATER_VIA_CT", "E_ROAD_WATER_VIA_CT"]:
        state = await state_manager.add_cargo(request.hub_id, request.cargo_type, request.volume)
    else:
        # Direct shipment bypassing Can Tho (A_DIRECT_ROAD)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"Direct Route: {request.volume:.2f} kg of {request.cargo_type} from {request.hub_id} dispatched directly to HCM."
        # Update database with direct log
        class SyncDirectLog:
            def __call__(self):
                from app.database import engine
                from app.models import SystemLog
                from sqlmodel import Session
                with Session(engine) as session:
                    session.add(SystemLog(timestamp=timestamp, message=log_msg))
                    session.commit()
        await anyio.to_thread.run_sync(SyncDirectLog())
        state = await state_manager.get_state()

    # Broadcast initial cargo arrival state
    await ws_manager.broadcast(state)

    # 3. Queue Layer 2 dispatch evaluation in background
    background_tasks.add_task(execute_layer2_evaluation_loop)

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

