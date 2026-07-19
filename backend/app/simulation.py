import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from app.database import engine
from app.models import Order, CargoInventory, SystemLog, Vehicle
from app.state import state_manager
from app.routes.websocket import ws_manager

logger = logging.getLogger(__name__)

# Initialize SYSTEM_CLOCK as timezone-aware ICT (+07:00)
SYSTEM_CLOCK = datetime.now(timezone(timedelta(hours=7)))
TIME_ACCELERATION_FACTOR = 1

async def run_simulation_loop(stop_event: asyncio.Event):
    global SYSTEM_CLOCK, TIME_ACCELERATION_FACTOR
    
    # Wait for database initialization
    await asyncio.sleep(2.0)
    logger.info("Simulation loop started.")
    
    while not stop_event.is_set():
        try:
            # 1. Increment SYSTEM_CLOCK by TIME_ACCELERATION_FACTOR hours
            SYSTEM_CLOCK += timedelta(hours=TIME_ACCELERATION_FACTOR)
            logger.info(f"Simulation Tick: clock={SYSTEM_CLOCK.isoformat()}, factor={TIME_ACCELERATION_FACTOR}")
            
            # 2. Query DB for shipments where state == "routed_to_can_tho" and eta_can_tho <= SYSTEM_CLOCK
            status_changed = False
            with Session(engine) as session:
                orders = session.exec(select(Order).where(Order.state == "routed_to_can_tho")).all()
                for order in orders:
                    if not order.eta_can_tho:
                        continue
                    try:
                        eta = datetime.fromisoformat(order.eta_can_tho)
                        if eta.tzinfo is None:
                            eta = eta.replace(tzinfo=timezone(timedelta(hours=7)))
                    except Exception:
                        continue
                    
                    if eta <= SYSTEM_CLOCK:
                        # Direct route vs via Can Tho transshipment route
                        is_direct = order.selected_route_id == "A_DIRECT_ROAD"
                        
                        if is_direct:
                            # 1. Flip directly to delivered
                            order.state = "delivered"
                            order.actual_arrival_at = eta.isoformat()
                            session.add(order)
                            
                            # 2. Return vehicle to available status at Can Tho
                            if order.assigned_vehicle_id:
                                veh = session.get(Vehicle, order.assigned_vehicle_id)
                                if veh:
                                    veh.status = "available"
                                    veh.location = "can_tho"
                                    session.add(veh)
                            
                            # 3. Log direct arrival
                            timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
                            log_msg = f"Direct Delivery: Shipment #{order.id} ({order.khoi_luong_kg:.1f} kg) successfully delivered directly to TP.HCM from {order.hub_id}."
                            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                        else:
                            # Transshipment via Can Tho
                            order.state = "arrived_waiting"
                            order.actual_arrival_at = eta.isoformat()
                            order.actual_weight_kg = order.khoi_luong_kg
                            session.add(order)
                            
                            # Set vehicle status back to available at Can Tho
                            if order.assigned_vehicle_id:
                                veh = session.get(Vehicle, order.assigned_vehicle_id)
                                if veh:
                                    veh.status = "available"
                                    veh.location = "can_tho"
                                    session.add(veh)
                            
                            # Accumulate in CargoInventory
                            from app.ai.normalizers import classify_priority
                            priority = classify_priority(order.commodity_id, order.loai_hang)
                            cargo_type = priority["tier"]
                            
                            inv = session.get(CargoInventory, cargo_type)
                            if not inv:
                                inv = CargoInventory(cargo_type=cargo_type, volume=0.0)
                                session.add(inv)
                            inv.volume += order.khoi_luong_kg
                            
                            # Log arrival at Can Tho Hub
                            timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
                            log_msg = f"Hub Incoming: Shipment #{order.id} ({order.khoi_luong_kg:.1f} kg of {order.commodity_id or order.loai_hang}) arrived at Can Tho Hub from {order.hub_id}."
                            session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                        
                        status_changed = True
                
                # 2b. Query DB for active dispatches to HCMC
                from app.models import DispatchOrder
                
                dispatches = session.exec(select(DispatchOrder).where(DispatchOrder.status != "completed")).all()
                for dispatch in dispatches:
                    if not dispatch.eta_hcm:
                        continue
                    try:
                        eta = datetime.fromisoformat(dispatch.eta_hcm)
                        if eta.tzinfo is None:
                            eta = eta.replace(tzinfo=timezone(timedelta(hours=7)))
                    except Exception:
                        continue
                    
                    if eta <= SYSTEM_CLOCK:
                        # Outbound arrived at HCM Market!
                        dispatch.status = "completed"
                        session.add(dispatch)
                        
                        # Set vehicle status back to available at Can Tho
                        veh = session.get(Vehicle, dispatch.vehicle_id)
                        if veh:
                            veh.status = "available"
                            veh.location = "can_tho"
                            session.add(veh)
                            
                        # Set all orders to delivered
                        shipment_ids = json.loads(dispatch.shipment_ids_json) if dispatch.shipment_ids_json else []
                        for s_id in shipment_ids:
                            order = session.get(Order, int(s_id))
                            if order:
                                order.state = "delivered"
                                order.actual_arrival_at = eta.isoformat()
                                session.add(order)
                        
                        # Log dispatch completion
                        timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
                        log_msg = f"Outbound Delivered: Dispatch #{dispatch.proposal_id} ({dispatch.total_weight_kg:.1f} kg) successfully delivered at HCM Market via vehicle {dispatch.vehicle_id}."
                        session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                        status_changed = True
                    else:
                        # Check if it should start moving
                        try:
                            dep = datetime.fromisoformat(dispatch.dispatched_at) if dispatch.dispatched_at else datetime.fromisoformat(dispatch.created_at)
                            if dep.tzinfo is None:
                                dep = dep.replace(tzinfo=timezone(timedelta(hours=7)))
                        except Exception:
                            dep = SYSTEM_CLOCK
                            
                        if dep <= SYSTEM_CLOCK < eta:
                            if dispatch.status == "waiting_for_pickup":
                                dispatch.status = "dispatching_to_hcm"
                                session.add(dispatch)
                                
                                # Set vehicle status to en_route/in_transit
                                veh = session.get(Vehicle, dispatch.vehicle_id)
                                if veh:
                                    veh.status = "en_route"
                                    session.add(veh)
                                
                                timestamp_log = SYSTEM_CLOCK.strftime("%Y-%m-%d %H:%M:%S")
                                log_msg = f"Outbound Transit: Dispatch #{dispatch.proposal_id} departed Can Tho Hub en route to TP.HCM via vehicle {dispatch.vehicle_id}."
                                session.add(SystemLog(timestamp=timestamp_log, message=log_msg))
                                status_changed = True
                
                if status_changed:
                    session.commit()
            
            # 3. If statuses changed, run AI Layer 2 Decision Engine
            if status_changed:
                await state_manager.evaluate_and_dispatch(SYSTEM_CLOCK)
            
            # 4. Broadcast TIME_TICK event
            current_state = await state_manager.get_state()
            state_data = current_state.model_dump(mode="json")
            
            # Get latest logistics overview and fleet details to send a fully synchronized state payload
            from app.services.ai2_client import get_deliveries, get_jobs
            from app.services.map_data import logistics_overview_payload, fleet_rows
            
            jobs, live = get_jobs()
            deliveries = get_deliveries()
            logistics = logistics_overview_payload(jobs, deliveries)
            fleet = fleet_rows()
            
            payload = {
                "event": "TIME_TICK",
                "system_clock": SYSTEM_CLOCK.isoformat(),
                "time_acceleration_factor": TIME_ACCELERATION_FACTOR,
                "data": state_data,
                "logistics_overview": logistics,
                "fleet": fleet,
                **state_data
            }
            
            # Broadcast to all connected clients
            await ws_manager.broadcast_event("TIME_TICK", payload)
            
        except Exception as e:
            logger.exception(f"Error in simulation loop: {e}")
            
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
