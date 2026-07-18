from datetime import datetime
from typing import Dict, List, Tuple
import anyio
from sqlmodel import Session, select
from app.config import CANTHO_DISPATCH_THRESHOLD_KG, CARGO_TYPES
from app.database import engine
from app.models import CargoInventory, SystemLog, SystemSettings, SystemState

class SystemStateManager:
    """
    Manages SQLite database transactions using SQLModel.
    Exposes async wrapper methods to prevent blocking the FastAPI event loop.
    """

    # ----------------- Sync Database Operations -----------------

    def _sync_get_state(self) -> SystemState:
        with Session(engine) as session:
            # 1. Fetch inventory
            inventory_map = {c: 0.0 for c in CARGO_TYPES}
            inventories = session.exec(select(CargoInventory)).all()
            for inv in inventories:
                if inv.cargo_type in inventory_map:
                    inventory_map[inv.cargo_type] = inv.volume

            # 2. Fetch settings
            weather_setting = session.get(SystemSettings, "weather")
            weather = weather_setting.value if weather_setting else "Clear"

            dispatch_setting = session.get(SystemSettings, "dispatch_status")
            dispatch_status = dispatch_setting.value if dispatch_setting else "WAIT"

            # 3. Fetch latest 20 logs
            logs_db = session.exec(select(SystemLog).order_by(SystemLog.id.desc()).limit(20)).all()
            logs = [{"timestamp": log.timestamp, "message": log.message} for log in reversed(logs_db)]

            # 4. Generate last updated timestamp
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if logs_db:
                last_updated = logs_db[0].timestamp

            return SystemState(
                inventory=inventory_map,
                dispatch_status=dispatch_status,
                weather=weather,
                logs=logs,
                last_updated=last_updated
            )

    def _sync_add_cargo(self, hub_id: str, cargo_type: str, volume: float) -> SystemState:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Session(engine) as session:
            # Update inventory
            inv = session.get(CargoInventory, cargo_type)
            if not inv:
                inv = CargoInventory(cargo_type=cargo_type, volume=0.0)
                session.add(inv)
            inv.volume += volume

            # Insert activity log
            log_msg = f"Hub Incoming: Received {volume:.2f} kg of {cargo_type} from {hub_id}."
            session.add(SystemLog(timestamp=timestamp, message=log_msg))
            session.commit()
            
        return self._sync_get_state()

    def _sync_set_weather(self, weather: str) -> SystemState:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Session(engine) as session:
            weather_setting = session.get(SystemSettings, "weather")
            if weather_setting:
                if weather_setting.value != weather:
                    log_msg = f"Weather Update: Climate shifted from {weather_setting.value} to {weather}."
                    weather_setting.value = weather
                    session.add(SystemLog(timestamp=timestamp, message=log_msg))
            else:
                session.add(SystemSettings(key="weather", value=weather))
                log_msg = f"Weather Initialized: Setting state to {weather}."
                session.add(SystemLog(timestamp=timestamp, message=log_msg))
            
            session.commit()
        return self._sync_get_state()

    def _sync_evaluate_and_dispatch(self) -> Tuple[SystemState, bool]:
        """
        Runs the actual Layer 2 dispatch forecasting engine for ROAD and WATER outbound pipelines.
        If any pipeline decisions return DISPATCH_NOW, updates the DB order states, resets cargo metrics, and marks vehicles.
        """
        from app.routes.layer2 import store, DEFAULT_CONFIG
        from app.ai.forecast_dispatch import decision_engine
        from app.ai.forecast_dispatch.enums import Mode, Decision
        from app.models import Order as DBOrder, Vehicle as DBVehicle
        from datetime import timezone

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_utc = datetime.now(timezone.utc)
        dispatch_occurred = False
        
        with Session(engine) as session:
            for outbound_mode in [Mode.ROAD, Mode.WATER]:
                result = decision_engine.evaluate(store, now_utc, outbound_mode, DEFAULT_CONFIG)
                
                if result.decision == Decision.DISPATCH_NOW:
                    dispatch_occurred = True
                    
                    # 1. Update all waiting shipments for this mode to dispatched state in SQLite DB
                    pending_shipments = store.pending_shipments(outbound_mode)
                    for ship in pending_shipments:
                        order_id = int(ship.shipment_id) if ship.shipment_id.isdigit() else None
                        if order_id:
                            order = session.get(DBOrder, order_id)
                            if order:
                                order.state = "dispatched"
                                order.dispatched_at = now_utc.isoformat()
                                session.add(order)

                    
                    # 2. Reset the inventory tracking metrics (compatible with old UI charts)
                    inventories = session.exec(select(CargoInventory)).all()
                    for inv in inventories:
                        inv.volume = 0.0
                        session.add(inv)
                    
                    # 3. Mark selected vehicle as en_route
                    if result.selected_vehicle:
                        veh = session.get(DBVehicle, result.selected_vehicle.vehicle_id)
                        if veh:
                            veh.status = "en_route"
                            session.add(veh)

                    # Update dispatch status key temporarily to trigger UI events
                    dispatch_setting = session.get(SystemSettings, "dispatch_status")
                    if dispatch_setting:
                        dispatch_setting.value = "DISPATCH"
                    else:
                        session.add(SystemSettings(key="dispatch_status", value="DISPATCH"))

                    # Log dispatch event
                    session.add(SystemLog(timestamp=timestamp, message=f"LAYER 2 DECISION ({outbound_mode.value.upper()}): DISPATCH. {result.explanation}"))
                else:
                    # Log wait decision details
                    session.add(SystemLog(timestamp=timestamp, message=f"LAYER 2 DECISION ({outbound_mode.value.upper()}): WAIT. {result.explanation}"))

            if dispatch_occurred:
                # Revert status to WAIT for the next orchestration cycle
                dispatch_setting = session.get(SystemSettings, "dispatch_status")
                if dispatch_setting:
                    dispatch_setting.value = "WAIT"

            session.commit()

        return self._sync_get_state(), dispatch_occurred



    # ----------------- Async Interface Wrappers -----------------

    async def get_state(self) -> SystemState:
        return await anyio.to_thread.run_sync(self._sync_get_state)

    async def add_cargo(self, hub_id: str, cargo_type: str, volume: float) -> SystemState:
        return await anyio.to_thread.run_sync(self._sync_add_cargo, hub_id, cargo_type, volume)

    async def set_weather(self, weather: str) -> SystemState:
        return await anyio.to_thread.run_sync(self._sync_set_weather, weather)

    async def evaluate_and_dispatch(self) -> Tuple[SystemState, bool]:
        return await anyio.to_thread.run_sync(self._sync_evaluate_and_dispatch)


# Global Singleton State Manager
state_manager = SystemStateManager()
