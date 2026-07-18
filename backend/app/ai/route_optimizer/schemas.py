from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


RouteCode = Literal[
    "A_DIRECT_ROAD",
    "B_ROAD_VIA_CT",
    "C_WATER_ROAD_VIA_CT",
    "D_WATER_VIA_CT",
    "E_ROAD_WATER_VIA_CT",
]


class RouteOptimizeRequest(BaseModel):
    order_id: Optional[str] = None
    hub_id: str
    commodity_id: Optional[str] = None
    loai_hang: Optional[str] = ""
    khoi_luong_kg: float = Field(gt=0)
    timestamp: str
    deadline_ts: Optional[str] = None  # Cung cấp hạn chót giao hàng động từ API/DB


class Priority(BaseModel):
    tier: str
    score: float
    label: str


class CostBreakdown(BaseModel):
    raw_transport_cost_vnd: float
    spoilage_cost_vnd: float
    transshipment_fee_vnd: float
    total_cost_vnd: float
    pricing_source: Optional[str] = None


class PhuongAn(BaseModel):
    ten: str
    route_code: RouteCode
    chi_phi_du_doan_vnd: Optional[float]
    thoi_gian_du_kien_gio: Optional[float]
    trang_thai: Literal["available", "currently_unavailable"]
    ly_do: Optional[str] = None
    cost_breakdown: Optional[CostBreakdown] = None


class Evidence(BaseModel):
    weather_ts: Optional[str] = None
    price_ts: Optional[str] = None


class RouteOptimizeResponse(BaseModel):
    hub_id: str
    priority: Priority
    recommended_route: Optional[RouteCode]
    phuong_an: list[PhuongAn]
    khuyen_nghi: Optional[str]
    evidence: Evidence
