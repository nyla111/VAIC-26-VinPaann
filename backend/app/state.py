from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import threading
import uuid
from dataclasses import asdict
import anyio
from sqlmodel import Session, select
from app.config import CANTHO_DISPATCH_THRESHOLD_KG, CARGO_TYPES
from app.database import engine
from app.models import CargoInventory, DispatchOrder, Order, SystemLog, SystemSettings, SystemState, Vehicle


def _select_dispatch_batch(shipments: list, capacity_kg: float) -> list:
    """Select an oldest-first batch that fits the selected vehicle.

    Layer 2 evaluates the aggregate queue, but one dispatch record represents
    one physical vehicle. The integration must therefore avoid marking every
    waiting order as dispatched when the queue is larger than that vehicle.
    """
    if capacity_kg <= 0:
        return []

    selected = []
    remaining = capacity_kg
    for shipment in sorted(shipments, key=lambda item: item.urgency_reference_ts):
        weight = max(float(shipment.effective_weight_kg), 0.0)
        if weight <= remaining + 1e-6:
            selected.append(shipment)
            remaining -= weight
    return selected


class SystemStateManager:
    """
    Manages SQLite database transactions using SQLModel.
    Exposes async wrapper methods to prevent blocking the FastAPI event loop.
    """

    def __init__(self) -> None:
        self._dispatch_lock = threading.Lock()

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

    def _sync_evaluate_and_dispatch(self, decision_ts: Optional[datetime] = None) -> Tuple[SystemState, bool]:
        """
        Runs the actual Layer 2 dispatch forecasting engine for ROAD and WATER outbound pipelines.
        If any pipeline decisions return DISPATCH_NOW, updates the DB order states, resets cargo metrics, and marks vehicles.
        """
        from app.routes.layer2 import store, DEFAULT_CONFIG
        from app.ai.forecast_dispatch import decision_engine
        from app.ai.forecast_dispatch.enums import Mode, Decision
        from datetime import timezone

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_utc = decision_ts or datetime.now(timezone.utc)
        dispatch_occurred = False
        
        # A single process may receive several arrival events concurrently.
        # Serialize the decision/commit boundary so the same vehicle cannot be
        # selected by two overlapping evaluations.
        with self._dispatch_lock, Session(engine) as session:
            for outbound_mode in [Mode.ROAD, Mode.WATER]:
                result = decision_engine.evaluate(store, now_utc, outbound_mode, DEFAULT_CONFIG)
                
                if result.decision == Decision.DISPATCH_NOW and result.selected_vehicle:
                    # One vehicle cannot carry the complete queue when the
                    # aggregate load exceeds its capacity. Keep the remainder
                    # in arrived_waiting for the next evaluation.
                    pending_shipments = store.pending_shipments(outbound_mode)
                    # A provider-accepted order is held for the provider's
                    # explicit dispatch action. This prevents the background
                    # supervisor from silently changing its carrier/vehicle.
                    provider_accepted_ids = {
                        str(order.id)
                        for order in session.exec(
                            select(Order).where(
                                Order.state == "arrived_waiting",
                                Order.provider_assignment_status == "accepted",
                            )
                        ).all()
                    }
                    pending_shipments = [
                        shipment
                        for shipment in pending_shipments
                        if shipment.shipment_id not in provider_accepted_ids
                    ]
                    batch = _select_dispatch_batch(
                        pending_shipments,
                        result.selected_vehicle.capacity_kg,
                    )
                    shipment_ids: list[str] = []
                    batch_weight = sum(ship.effective_weight_kg for ship in batch)
                    if batch:
                        dispatch_occurred = True
                        selected_vehicle_record = session.get(
                            Vehicle,
                            result.selected_vehicle.vehicle_id,
                        )
                        selected_provider_id = (
                            selected_vehicle_record.provider_id
                            if selected_vehicle_record is not None
                            else None
                        )
                        for ship in batch:
                            order_id = int(ship.shipment_id) if ship.shipment_id.isdigit() else None
                            if order_id:
                                order = session.get(Order, order_id)
                                if order:
                                    order.state = "dispatched"
                                    order.dispatched_at = now_utc.isoformat()
                                    order.assigned_vehicle_id = result.selected_vehicle.vehicle_id
                                    order.assigned_provider_id = selected_provider_id
                                    order.provider_assignment_status = "assigned"
                                    order.provider_assigned_at = now_utc.isoformat()
                                    order.reason_codes_json = json.dumps([code.value for code in result.reason_codes])
                                    order.priority_score_json = (
                                        json.dumps(asdict(result.priority_score))
                                        if result.priority_score is not None else None
                                    )
                                    order.predicted_full_load_time = (
                                        result.forecast.predicted_full_load_time.isoformat()
                                        if result.forecast.predicted_full_load_time else None
                                    )
                                    shipment_ids.append(ship.shipment_id)
                                    session.add(order)

                                    # Keep the compatibility inventory metric in
                                    # sync without erasing cargo that remains
                                    # in the consolidation queue.
                                    from app.ai.normalizers import classify_priority
                                    cargo_type = classify_priority(order.commodity_id, order.loai_hang)["tier"]
                                    inventory = session.get(CargoInventory, cargo_type)
                                    if inventory:
                                        inventory.volume = max(
                                            0.0,
                                            inventory.volume - ship.effective_weight_kg,
                                        )
                                        session.add(inventory)

                        veh = selected_vehicle_record
                        if veh:
                            veh.status = "in_transit"
                            session.add(veh)

                        proposal_id = f"dispatch_{uuid.uuid4().hex}"
                        dispatch = DispatchOrder(
                            proposal_id=proposal_id,
                            vehicle_id=result.selected_vehicle.vehicle_id,
                            outbound_mode=outbound_mode.value,
                            shipment_ids_json=json.dumps(shipment_ids),
                            total_weight_kg=batch_weight,
                            capacity_kg=result.selected_vehicle.capacity_kg,
                            fill_ratio=min(batch_weight / result.selected_vehicle.capacity_kg, 1.0),
                            predicted_full_load_time=(
                                result.forecast.predicted_full_load_time.isoformat()
                                if result.forecast.predicted_full_load_time else None
                            ),
                            reason_codes_json=json.dumps([code.value for code in result.reason_codes]),
                            priority_score_json=(
                                json.dumps(asdict(result.priority_score))
                                if result.priority_score is not None else None
                            ),
                            created_at=timestamp,
                            dispatched_at=now_utc.isoformat(),
                            eta_hcm=(now_utc + timedelta(hours=5)).isoformat(),
                        )
                        session.add(dispatch)
                        for shipment_id in shipment_ids:
                            order = session.get(Order, int(shipment_id))
                            if order:
                                order.dispatch_proposal_id = proposal_id
                                session.add(order)

                        # Update dispatch status key temporarily to trigger UI events
                        dispatch_setting = session.get(SystemSettings, "dispatch_status")
                        if dispatch_setting:
                            dispatch_setting.value = "DISPATCH"
                        else:
                            session.add(SystemSettings(key="dispatch_status", value="DISPATCH"))

                        # Log dispatch event
                        session.add(SystemLog(timestamp=timestamp, message=f"LAYER 2 DECISION ({outbound_mode.value.upper()}): DISPATCH. {result.explanation}"))
                    else:
                        session.add(SystemLog(
                            timestamp=timestamp,
                            message=(
                                f"LAYER 2 DECISION ({outbound_mode.value.upper()}): WAIT. "
                                "No waiting batch fits the selected vehicle capacity."
                            ),
                        ))
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

    async def evaluate_and_dispatch(self, decision_ts: Optional[datetime] = None) -> Tuple[SystemState, bool]:
        return await anyio.to_thread.run_sync(self._sync_evaluate_and_dispatch, decision_ts)

    def _sync_record_ai_error(self, message: str) -> SystemState:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Session(engine) as session:
            session.add(SystemLog(
                timestamp=timestamp,
                message=f"AI2 ERROR: {message}",
                event_type="AI_ERROR",
                level="ERROR",
            ))
            session.commit()
        return self._sync_get_state()

    async def record_ai_error(self, message: str) -> SystemState:
        return await anyio.to_thread.run_sync(self._sync_record_ai_error, message)


# Global Singleton State Manager
state_manager = SystemStateManager()
