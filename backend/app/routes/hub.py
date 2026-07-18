import random
from datetime import datetime
import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.config import CARGO_TYPES, HUBS, WEATHER_CONDITIONS
from app.models import RouteSelectRequest, SystemState
from app.state import state_manager
from app.routes.websocket import ws_manager
from app.ai.layer1_helper import predict_routes

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
    
    # 2. Accumulate cargo if routed via Can Tho
    if request.selected_route_id in ["cantho_road", "cantho_waterway"]:
        state = await state_manager.add_cargo(request.hub_id, request.cargo_type, request.volume)
    else:
        # Direct shipment bypassing Can Tho
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"Direct Route: {request.volume:.2f} tons of {request.cargo_type} from {request.hub_id} dispatched directly to HCM."
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
    provincial_hubs = [h for h in HUBS if h != "Can Tho"]
    hub = random.choice(provincial_hubs)
    cargo = random.choice(CARGO_TYPES)
    volume = round(random.uniform(5.0, 25.0), 2)
    urgency = random.choice(["Low", "Medium", "High"])
    weather = random.choice(WEATHER_CONDITIONS)

    # 1. Call Layer 1 Optimizer to get recommended route
    options = predict_routes(hub, cargo, volume, urgency, weather)
    recommended_option = next(opt for opt in options if opt.recommendation_flag)

    # 2. Structure RouteSelectRequest payload
    select_payload = RouteSelectRequest(
        hub_id=hub,
        selected_route_id=recommended_option.route_id,
        cargo_type=cargo,
        volume=volume,
        weather=weather
    )

    # 3. Register route selection and add to background task
    # We call select_route directly
    state = await select_route(select_payload, background_tasks)

    return {
        "message": f"Simulation Event Triggered: Inbound cargo from {hub}.",
        "cargo_details": {
            "origin": hub,
            "cargo_type": cargo,
            "volume_tons": volume,
            "urgency": urgency,
            "weather": weather
        },
        "optimized_decision": {
            "route_id": recommended_option.route_id,
            "route_name": recommended_option.route_name,
            "recommendation_reason": recommended_option.reason
        },
        "current_system_state": state
    }
