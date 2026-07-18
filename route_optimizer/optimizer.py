from __future__ import annotations

from pathlib import Path
from datetime import timedelta
from typing import Any

from .candidates import build_candidates
from .data_loader import DEFAULT_DATA_DIR, load_data, parse_ts
from .feasibility import evaluate_route_feasibility
from .normalizers import classify_priority, to_node_id
from .pricing import price_route


def optimize_route(input_data: dict[str, Any], data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    store = load_data(Path(data_dir))
    hub_id = to_node_id(input_data.get("hub_id"))
    if hub_id is None:
        raise ValueError(f"Unknown hub_id/slug/name: {input_data.get('hub_id')}")
    if hub_id not in {"HUB_VITHANH", "HUB_LONGXUYEN", "HUB_SOCTRANG", "HUB_VINHLONG"}:
        raise ValueError(f"Input hub must be a collection hub, got {hub_id}")

    commodity_id = input_data.get("commodity_id")
    loai_hang = input_data.get("loai_hang") or ""
    khoi_luong_kg = float(input_data["khoi_luong_kg"])
    decision_ts = parse_ts(input_data["timestamp"])
    commodity = store.commodities.get(commodity_id) if commodity_id else None
    priority = classify_priority(commodity_id, loai_hang)
    order = store.orders.get(input_data.get("order_id")) if input_data.get("order_id") else None
    deadline_ts = parse_ts(order["deadline_ts"]) if order and order.get("deadline_ts") else None

    phuong_an = []
    weather_ts = None
    price_ts = None
    for candidate in build_candidates(hub_id, store.legs):
        feasible, reason, adjusted_duration, candidate_weather_ts = evaluate_route_feasibility(
            store, candidate.leg_ids, commodity, decision_ts
        )
        weather_ts = candidate_weather_ts or weather_ts
        if not feasible:
            item = {
                "ten": candidate.ten,
                "route_code": candidate.route_code,
                "chi_phi_du_doan_vnd": None,
                "thoi_gian_du_kien_gio": None,
                "trang_thai": "currently_unavailable",
                "ly_do": reason,
            }
            phuong_an.append(item)
            continue

        if deadline_ts is not None and decision_ts + timedelta(hours=adjusted_duration) > deadline_ts:
            phuong_an.append(
                {
                    "ten": candidate.ten,
                    "route_code": candidate.route_code,
                    "chi_phi_du_doan_vnd": None,
                    "thoi_gian_du_kien_gio": None,
                    "trang_thai": "currently_unavailable",
                    "ly_do": "vuot_deadline",
                }
            )
            continue

        cost, price_reason, candidate_price_ts, cost_breakdown = price_route(
            store,
            candidate.leg_ids,
            commodity_id,
            loai_hang,
            khoi_luong_kg,
            adjusted_duration,
            decision_ts,
        )
        price_ts = candidate_price_ts or price_ts
        if cost is None:
            phuong_an.append(
                {
                    "ten": candidate.ten,
                    "route_code": candidate.route_code,
                    "chi_phi_du_doan_vnd": None,
                    "thoi_gian_du_kien_gio": None,
                    "trang_thai": "currently_unavailable",
                    "ly_do": price_reason,
                }
            )
            continue
        phuong_an.append(
            {
                "ten": candidate.ten,
                "route_code": candidate.route_code,
                "chi_phi_du_doan_vnd": cost,
                "thoi_gian_du_kien_gio": round(adjusted_duration, 2),
                "trang_thai": "available",
                "cost_breakdown": cost_breakdown,
            }
        )

    available = [item for item in phuong_an if item["trang_thai"] == "available"]
    winner = min(available, key=lambda item: item["chi_phi_du_doan_vnd"]) if available else None
    return {
        "hub_id": hub_id,
        "priority": priority,
        "recommended_route": winner["route_code"] if winner else None,
        "phuong_an": phuong_an,
        "khuyen_nghi": winner["ten"] if winner else None,
        "evidence": {
            "weather_ts": weather_ts,
            "price_ts": price_ts,
        },
    }
