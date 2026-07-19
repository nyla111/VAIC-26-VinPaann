"""Backend-only lifecycle helpers shared by route-selection entry points."""

import json
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import DispatchOrder, Order, Vehicle


def create_direct_dispatch(
    session: Session,
    order: Order,
    dispatched_at: datetime,
) -> DispatchOrder | None:
    """Create the durable dispatch record for an order that bypasses Can Tho."""
    vehicle = session.exec(
        select(Vehicle).where(
            Vehicle.mode == "road",
            Vehicle.status == "available",
            Vehicle.location == "can_tho",
        )
    ).first()
    if not vehicle:
        vehicle = session.exec(select(Vehicle).where(Vehicle.mode == "road")).first()
    if not vehicle:
        return None

    if order.id is None:
        session.flush()

    eta_hours = max(float(order.selected_route_eta_hours or 5.0), 0.01)
    dispatched_at_iso = dispatched_at.isoformat()
    order.state = "dispatched"
    order.dispatched_at = dispatched_at_iso
    order.assigned_vehicle_id = vehicle.license_plate
    order.assigned_provider_id = vehicle.provider_id
    order.provider_assignment_status = "assigned"
    order.provider_assigned_at = dispatched_at_iso
    vehicle.status = "in_transit"
    session.add(vehicle)
    session.add(order)

    dispatch = DispatchOrder(
        proposal_id=f"direct_{order.id}",
        vehicle_id=vehicle.license_plate,
        outbound_mode="road",
        shipment_ids_json=json.dumps([str(order.id)]),
        total_weight_kg=order.khoi_luong_kg,
        capacity_kg=vehicle.capacity_kg,
        fill_ratio=min(order.khoi_luong_kg / vehicle.capacity_kg, 1.0),
        status="waiting_for_pickup",
        created_at=dispatched_at_iso,
        dispatched_at=dispatched_at_iso,
        eta_hcm=(dispatched_at + timedelta(hours=eta_hours)).isoformat(),
    )
    session.add(dispatch)
    return dispatch
