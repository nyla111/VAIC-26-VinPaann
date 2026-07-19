"""Role-scoped order reads shared by the enterprise, logistics and admin APIs.

The order table is intentionally the source of truth.  Vehicle ownership is
used only as a backwards-compatible fallback for orders created before
``assigned_provider_id`` was introduced.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlmodel import Session, select

from app.mappings import enrich_order_payload, get_provider_name
from app.models import Order, User, Vehicle


def _user_value(user: User | dict[str, Any], key: str) -> Any:
    if isinstance(user, dict):
        return user.get(key)
    return getattr(user, key, None)


def _legacy_provider_id(order: Order, vehicle_by_plate: dict[str, Vehicle]) -> int | None:
    if order.assigned_provider_id is not None:
        return order.assigned_provider_id
    if order.assigned_vehicle_id:
        vehicle = vehicle_by_plate.get(order.assigned_vehicle_id)
        return vehicle.provider_id if vehicle else None
    return None


def can_view_order(
    order: Order,
    user: User | dict[str, Any],
    vehicle_by_plate: dict[str, Vehicle] | None = None,
) -> bool:
    """Return whether a role may read an order or start its tracking stream."""

    role = _user_value(user, "role")
    user_id = _user_value(user, "id")
    if role == "admin":
        return True
    if role == "enterprise":
        return order.user_id is not None and order.user_id == user_id
    if role == "logistics":
        vehicles = vehicle_by_plate or {}
        return _legacy_provider_id(order, vehicles) == user_id
    return False


def visible_orders(session: Session, user: User | dict[str, Any]) -> list[Order]:
    """Load only orders visible to ``user``.

    The Python-side filter deliberately keeps the legacy vehicle fallback
    explicit and easy to audit.  It also avoids a provider seeing an order
    merely because its vehicle happens to be available in the fleet.
    """

    orders = session.exec(select(Order).order_by(Order.id.desc())).all()
    if _user_value(user, "role") == "admin":
        return orders

    vehicles = {
        vehicle.license_plate: vehicle
        for vehicle in session.exec(select(Vehicle)).all()
    }
    return [order for order in orders if can_view_order(order, user, vehicles)]


def order_projection(
    order: Order,
    session: Session,
    *,
    visibility_scope: str,
) -> dict[str, Any]:
    """Return the stable cross-role representation of an order."""

    payload = enrich_order_payload(order, session)
    vehicle = session.get(Vehicle, order.assigned_vehicle_id) if order.assigned_vehicle_id else None
    provider_id = order.assigned_provider_id
    if provider_id is None and vehicle is not None:
        provider_id = vehicle.provider_id

    payload.update(
        {
            "order_id": order.id,
            "owner_user_id": order.user_id,
            "provider_id": str(provider_id) if provider_id is not None else None,
            "provider_name": (
                get_provider_name(provider_id, session)
                if provider_id is not None
                else payload.get("provider_name")
            ),
            "provider_assignment_status": order.provider_assignment_status,
            "provider_assigned_at": order.provider_assigned_at,
            "assigned_vehicle_id": order.assigned_vehicle_id,
            "vehicle_mode": vehicle.mode if vehicle else None,
            "vehicle_capacity_kg": vehicle.capacity_kg if vehicle else None,
            "state_code": order.state,
            "visibility_scope": visibility_scope,
        }
    )
    return payload


def projection_scope(user: User | dict[str, Any]) -> str:
    role = _user_value(user, "role")
    return {
        "admin": "all_orders",
        "enterprise": "owned_orders",
        "logistics": "provider_assigned_orders",
    }.get(role, "none")


def project_orders(
    orders: Iterable[Order],
    session: Session,
    user: User | dict[str, Any],
) -> list[dict[str, Any]]:
    scope = projection_scope(user)
    return [order_projection(order, session, visibility_scope=scope) for order in orders]
