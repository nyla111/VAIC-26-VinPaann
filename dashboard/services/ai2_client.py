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
        return demo_jobs(), False
    try:
        with urlopen(f"{AI2_BASE_URL}/dispatch/jobs", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("jobs", []), True
    except Exception:
        return demo_jobs(), False


def get_deliveries() -> list[dict[str, Any]]:
    return [
        {"delivery_id": "DLV-001", "route_code": "A_DIRECT_ROAD", "status": "dang_chay", "eta": "2h 10m"},
        {"delivery_id": "DLV-002", "route_code": "D_WATER_VIA_CT", "status": "cho_boc_xep", "eta": "5h 40m"},
        {"delivery_id": "DLV-003", "route_code": "B_ROAD_VIA_CT", "status": "hoan_tat", "eta": "0h"},
    ]
