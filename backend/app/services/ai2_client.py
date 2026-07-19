from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.request import urlopen


AI2_AVAILABLE = os.getenv("AI2_AVAILABLE", "false").lower() == "true"
AI2_BASE_URL = os.getenv("AI2_BASE_URL", "http://localhost:8001")


def demo_jobs() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).astimezone().replace(microsecond=0)
    return [
        {
            "job_id": "JOB-DEMO-001",
            "hub_id": "HUB_VINHLONG",
            "khoi_luong_tich_luy_hien_tai_kg": 18450,
            "quyet_dinh": "gom_them_cho_du_tai",
            "thoi_gian_de_xuat_chay": (now + timedelta(hours=3)).isoformat(),
            "route_code": "A_DIRECT_ROAD",
        },
        {
            "job_id": "JOB-DEMO-002",
            "hub_id": "HUB_SOCTRANG",
            "khoi_luong_tich_luy_hien_tai_kg": 42600,
            "quyet_dinh": "xuat_ben_som",
            "thoi_gian_de_xuat_chay": (now + timedelta(hours=1)).isoformat(),
            "route_code": "D_WATER_VIA_CT",
        },
        {
            "job_id": "JOB-DEMO-003",
            "hub_id": "HUB_LONGXUYEN",
            "khoi_luong_tich_luy_hien_tai_kg": 9600,
            "quyet_dinh": "cho_them_don",
            "thoi_gian_de_xuat_chay": (now + timedelta(hours=5)).isoformat(),
            "route_code": "B_ROAD_VIA_CT",
        },
    ]


def get_jobs() -> tuple[list[dict[str, Any]], bool]:
    if not AI2_AVAILABLE:
        # The integrated supervisor is the local production implementation;
        # do not silently substitute fabricated jobs for a live dashboard.
        try:
            from app.ai.forecast_dispatch.enums import Mode
            from app.routes.layer2 import DEFAULT_CONFIG, store
            from app.ai.forecast_dispatch import decision_engine

            jobs: list[dict[str, Any]] = []
            for mode in (Mode.ROAD, Mode.WATER):
                result = decision_engine.evaluate(store, datetime.now(timezone.utc), mode, DEFAULT_CONFIG)
                for shipment in store.pending_shipments(mode):
                    jobs.append({
                        "job_id": f"ORDER-{shipment.shipment_id}",
                        "shipment_id": shipment.shipment_id,
                        "hub_id": shipment.hub_id,
                        "khoi_luong_tich_luy_hien_tai_kg": shipment.effective_weight_kg,
                        "quyet_dinh": result.decision.value,
                        "thoi_gian_de_xuat_chay": (
                            result.proposed_departure_time.isoformat()
                            if result.proposed_departure_time else None
                        ),
                        "predicted_full_load_time": (
                            result.forecast.predicted_full_load_time.isoformat()
                            if result.forecast.predicted_full_load_time else None
                        ),
                        "reason_codes": [code.value for code in result.reason_codes],
                        "route_code": shipment.selected_route.value,
                    })
            return jobs, True
        except Exception:
            return [], False
    try:
        with urlopen(f"{AI2_BASE_URL}/dispatch/jobs", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("jobs", []), True
    except Exception:
        return demo_jobs(), False


def get_deliveries() -> list[dict[str, Any]]:
    try:
        from sqlmodel import Session, select
        from app.database import engine
        from app.models import Order

        with Session(engine) as session:
            orders = session.exec(
                select(Order).where(Order.state.in_(["dispatched", "delivered"]))
            ).all()
            return [
                {
                    "delivery_id": f"ORDER-{order.id}",
                    "order_id": order.id,
                    "hub_id": order.hub_id,
                    "route_code": order.selected_route_id,
                    "status": order.state,
                    "eta": order.selected_route_eta_hours,
                }
                for order in orders
            ]
    except Exception:
        return []
