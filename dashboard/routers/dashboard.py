from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ..auth import current_user, require_user
from ..services.ai1_client import run_optimizer
from ..services.ai2_client import get_deliveries, get_jobs
from ..services.map_data import errors, fleet_rows, latest_weather, map_payload, optimizer_kpis, route_options_for_hub


router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="dashboard/templates")
TRACKING_PATH = Path("dashboard/session_orders.json")

ROLE_SECTIONS = {
    "business": ["business_shipment_form", "business_recommendations", "business_tracking"],
    "logistics": ["logistics_fleet", "logistics_jobs", "logistics_deliveries"],
    "admin": [
        "admin_inventory",
        "admin_weather",
        "admin_dispatch",
        "admin_simulation",
        "admin_logs",
        "business_shipment_form",
        "logistics_fleet",
    ],
}

SECTION_LABELS = {
    "business_shipment_form": "Shipment Form",
    "business_recommendations": "Recommendations/Analytics",
    "business_tracking": "Tracking",
    "logistics_fleet": "Fleet",
    "logistics_jobs": "Jobs",
    "logistics_deliveries": "Deliveries",
    "admin_inventory": "Inventory",
    "admin_weather": "Weather",
    "admin_dispatch": "Dispatch",
    "admin_simulation": "Simulation",
    "admin_logs": "Logs/Analytics",
}

DEFAULT_SECTION = {"business": "business_shipment_form", "logistics": "logistics_fleet", "admin": "admin_inventory"}

REASON_LABELS = {
    "hang_khong_phu_hop_duong_thuy": "Loại hàng không phù hợp vận chuyển đường thủy.",
    "muc_nuoc_khong_an_toan": "Mực nước hoặc điều kiện thủy văn chưa an toàn.",
    "khong_co_phuong_tien_phu_hop": "Chưa có phương tiện phù hợp về tải trọng/trạng thái.",
    "vuot_deadline": "Không đáp ứng được hạn giao hàng.",
    "missing_weather": "Thiếu dữ liệu thời tiết gần thời điểm quyết định.",
}

HUB_OPTIONS = [
    {"value": "HUB_VITHANH", "label": "Hub Vị Thanh"},
    {"value": "HUB_LONGXUYEN", "label": "Hub Long Xuyên"},
    {"value": "HUB_SOCTRANG", "label": "Hub Sóc Trăng"},
    {"value": "HUB_VINHLONG", "label": "Hub Vĩnh Long"},
]

COMMODITY_OPTIONS = [
    "COM_RICE",
    "COM_PANGASIUS",
    "COM_SHRIMP",
    "COM_POMELO",
    "COM_VEGETABLE",
    "COM_PURPLE_ONION",
]


class ShipmentPayload(BaseModel):
    hub_id: str
    commodity_id: str | None = None
    loai_hang: str = ""
    khoi_luong_kg: float = Field(gt=0)
    timestamp: str


def model_from_dict(model_cls, data: dict[str, Any]):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def allowed_sections(role: str) -> list[str]:
    return ROLE_SECTIONS[role]


def menu_for(role: str) -> list[dict[str, str]]:
    return [{"id": item, "label": SECTION_LABELS[item]} for item in allowed_sections(role)]


def section_template(section: str) -> str:
    return f"sections/{section}.html"


def load_tracking(username: str) -> list[dict[str, Any]]:
    if not TRACKING_PATH.exists():
        return []
    data = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    return data.get(username, [])


def save_tracking(username: str, item: dict[str, Any]) -> None:
    data = {}
    if TRACKING_PATH.exists():
        data = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    data.setdefault(username, []).insert(0, item)
    data[username] = data[username][:50]
    TRACKING_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def base_context(request: Request, user: dict[str, Any], section: str, extra: dict[str, Any] | None = None):
    context = {
        "request": request,
        "user": user,
        "role": user["role"],
        "section": section,
        "section_label": SECTION_LABELS[section],
        "section_template": section_template(section),
        "menu": menu_for(user["role"]),
        "reason_labels": REASON_LABELS,
    }
    if extra:
        context.update(extra)
    return context


def prepare_section_context(user: dict[str, Any], section: str) -> dict[str, Any]:
    if section == "business_tracking":
        return {"tracking": load_tracking(user["username"])}
    if section == "logistics_fleet":
        return {"fleet": fleet_rows(), "status_filter": ""}
    if section == "logistics_jobs":
        jobs, live = get_jobs()
        return {"jobs": jobs, "ai2_live": live}
    if section == "logistics_deliveries":
        return {"deliveries": get_deliveries()}
    if section == "admin_inventory":
        payload = map_payload()
        return {"kpis": optimizer_kpis(), "map_payload": payload, "map_payload_json": json.dumps(payload)}
    if section == "admin_weather":
        return {"weather": latest_weather()}
    if section == "admin_dispatch":
        jobs, live = get_jobs()
        return {"jobs": jobs, "ai2_live": live}
    if section == "admin_logs":
        kpis = optimizer_kpis()
        return {"errors": errors(), "kpis": kpis, "route_counts_json": json.dumps(kpis["route_counts"])}
    return {}


def api_context(user: dict[str, Any], section: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user": user,
        "role": user["role"],
        "section": section,
        "section_label": SECTION_LABELS[section],
        "menu": menu_for(user["role"]),
        "reason_labels": REASON_LABELS,
        "hub_options": HUB_OPTIONS,
        "commodity_options": COMMODITY_OPTIONS,
    }
    payload.update(prepare_section_context(user, section))
    if extra:
        payload.update(extra)
    return payload


def api_user(request: Request) -> dict[str, Any] | JSONResponse:
    user = current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    return user


@router.get("")
def dashboard(request: Request, section: str | None = None):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    section = section or DEFAULT_SECTION[user["role"]]
    if section not in allowed_sections(user["role"]):
        section = DEFAULT_SECTION[user["role"]]
    context = prepare_section_context(user, section)
    return templates.TemplateResponse(request=request, name="layout.html", context=base_context(request, user, section, context))


@router.post("/shipment")
def submit_shipment(
    request: Request,
    hub_id: str = Form(...),
    commodity_id: str = Form(""),
    loai_hang: str = Form(""),
    khoi_luong_kg: float = Form(...),
    timestamp: str = Form(...),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    input_data = {
        "hub_id": hub_id,
        "commodity_id": commodity_id or None,
        "loai_hang": loai_hang,
        "khoi_luong_kg": khoi_luong_kg,
        "timestamp": timestamp,
    }
    result = run_optimizer(input_data)
    save_tracking(
        user["username"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input": input_data,
            "recommended_route": result["recommended_route"],
            "khuyen_nghi": result["khuyen_nghi"],
            "routes": result["phuong_an"],
        },
    )
    section = "business_recommendations" if user["role"] != "admin" else "admin_simulation"
    route_map = route_options_for_hub(result["hub_id"])
    route_map["activeRoute"] = result["recommended_route"]
    context = {
        "result": result,
        "input_data": input_data,
        "route_map_json": json.dumps(route_map),
        **prepare_section_context(user, section),
    }
    return templates.TemplateResponse(request=request, name="layout.html", context=base_context(request, user, section, context))


@router.post("/fleet")
def filter_fleet(request: Request, status_filter: str = Form("")):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    rows = fleet_rows()
    if status_filter:
        rows = [row for row in rows if row["status"] == status_filter]
    context = {"fleet": rows, "status_filter": status_filter}
    return templates.TemplateResponse(
        request=request,
        name="layout.html",
        context=base_context(request, user, "logistics_fleet", context),
    )


@router.get("/map-data")
def map_data(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return JSONResponse(map_payload())


@router.get("/api/view")
def api_view(request: Request, section: str | None = None, status_filter: str = ""):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    section = section or DEFAULT_SECTION[user["role"]]
    if section not in allowed_sections(user["role"]):
        section = DEFAULT_SECTION[user["role"]]
    extra: dict[str, Any] = {}
    if section == "logistics_fleet":
        rows = fleet_rows()
        if status_filter:
            rows = [row for row in rows if row["status"] == status_filter]
        extra = {"fleet": rows, "status_filter": status_filter}
    return api_context(user, section, extra)


@router.post("/api/shipment")
async def api_submit_shipment(request: Request):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    payload = model_from_dict(ShipmentPayload, await request.json())
    input_data = {
        "hub_id": payload.hub_id,
        "commodity_id": payload.commodity_id or None,
        "loai_hang": payload.loai_hang,
        "khoi_luong_kg": payload.khoi_luong_kg,
        "timestamp": payload.timestamp,
    }
    result = run_optimizer(input_data)
    save_tracking(
        user["username"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input": input_data,
            "recommended_route": result["recommended_route"],
            "khuyen_nghi": result["khuyen_nghi"],
            "routes": result["phuong_an"],
        },
    )
    section = "business_recommendations" if user["role"] != "admin" else "admin_simulation"
    route_map = route_options_for_hub(result["hub_id"])
    route_map["activeRoute"] = result["recommended_route"]
    return api_context(user, section, {"result": result, "input_data": input_data, "route_map": route_map})


@router.get("/api/map-data")
def api_map_data(request: Request):
    user = api_user(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(map_payload())
