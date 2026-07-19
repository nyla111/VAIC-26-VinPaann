"""Authenticated, role-scoped order read APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import Session

from app.database import engine
from app.models import User
from app.routes.auth import current_user
from app.services.order_views import project_orders, visible_orders

router = APIRouter(prefix="/api/v1/orders")


def _require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


@router.get("")
def list_orders(
    request: Request,
    state: str | None = Query(default=None),
):
    """List orders visible to the logged-in role.

    Admin sees all orders, enterprise sees orders it created, and logistics
    sees orders assigned to its provider (including legacy vehicle-linked
    assignments).  No client-provided user/provider filter can widen scope.
    """

    user = _require_user(request)
    with Session(engine) as session:
        orders = visible_orders(session, user)
        if state:
            orders = [order for order in orders if order.state == state]
        return {
            "scope": {
                "role": user.role,
                "user_id": user.id,
            },
            "orders": project_orders(orders, session, user),
        }


@router.get("/{order_id}")
def get_order(order_id: int, request: Request):
    """Return one order only when it belongs to the caller's read scope."""

    user = _require_user(request)
    with Session(engine) as session:
        orders = [order for order in visible_orders(session, user) if order.id == order_id]
        if not orders:
            # Do not reveal whether another role owns the order.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return project_orders(orders, session, user)[0]
