import json
from typing import Any, Dict, Optional
from sqlmodel import Session, select
from app.models import User

# Mappings of User credentials to Real Names
ENTERPRISE_MAPPING = {
    "enterprise1@vaic.vn": "Cửu Long Rice Co.",
    "enterprise2@vaic.vn": "Tiền Giang Fruit Farm",
    "enterprise3@vaic.vn": "Đồng Tháp Seafood Ltd",
    "enterprise4@vaic.vn": "An Giang Organic Farm",
    "enterprise5@vaic.vn": "Vĩnh Long Agri Coop",
}

LOGISTICS_MAPPING = {
    "logistics1@vaic.vn": "Mekong Logistics",
    "logistics2@vaic.vn": "Southern Freight",
    "logistics3@vaic.vn": "Delta Waterway",
    "logistics4@vaic.vn": "Cần Thơ Trans",
    "logistics5@vaic.vn": "An Giang Transport",
}

HUB_NAME_MAPPING = {
    "HUB_VITHANH": "Vị Thanh Hub",
    "HUB_LONGXUYEN": "Long Xuyên Hub",
    "HUB_SOCTRANG": "Sóc Trăng Hub",
    "HUB_VINHLONG": "Vĩnh Long Hub",
    "CT_HUB": "Cần Thơ Hub",
    "HCM_MARKET": "TP. HCM",
}

def get_business_name(user_id: Optional[int], session: Session) -> str:
    if not user_id:
        return "Doanh nghiệp nông sản"
    user = session.get(User, user_id)
    if user:
        return ENTERPRISE_MAPPING.get(user.email, user.email)
    return "Doanh nghiệp nông sản"

def get_provider_name(provider_user_id: Optional[int], session: Session) -> str:
    if not provider_user_id:
        return "Unassigned"
    user = session.get(User, provider_user_id)
    if user:
        return LOGISTICS_MAPPING.get(user.email, user.email)
    return "Unassigned"

def enrich_order_payload(order: Any, session: Session) -> Dict[str, Any]:
    business_name = get_business_name(order.user_id, session)
    origin = HUB_NAME_MAPPING.get(order.hub_id, order.hub_id)
    destination = "TP. HCM"

    commodity_map = {
        "COM_RICE": "Rice",
        "COM_PANGASIUS": "Seafood",
        "COM_SHRIMP": "Seafood",
        "COM_POMELO": "Fruits",
        "COM_VEGETABLE": "Vegetables",
        "COM_PURPLE_ONION": "Vegetables",
    }
    commodity = commodity_map.get(order.commodity_id, order.loai_hang or "Agri-cargo")

    provider_name = None
    provider_id_str = None
    if order.assigned_vehicle_id:
        from app.models import Vehicle
        veh = session.get(Vehicle, order.assigned_vehicle_id)
        if veh and veh.provider_id:
            provider_id_str = str(veh.provider_id)
            provider_name = get_provider_name(veh.provider_id, session)

    status_map = {
        "created": "awaiting_assignment",
        "routed_to_can_tho": "in_transit",
        "arrived_waiting": "assigned",
        "dispatched": "in_transit",
        "delivered": "delivered",
    }
    status = status_map.get(order.state, order.state)

    route_options = []
    if order.route_options_json:
        try:
            raw_options = json.loads(order.route_options_json)
            for ro in raw_options:
                code = ro.get("route_code", "")
                if code == "A_DIRECT_ROAD":
                    modes = ["Road"]
                    transfers = 0
                elif code == "B_ROAD_VIA_CT":
                    modes = ["Road", "Road"]
                    transfers = 1
                elif code == "C_WATER_ROAD_VIA_CT":
                    modes = ["Water", "Road"]
                    transfers = 1
                elif code == "D_WATER_VIA_CT":
                    modes = ["Water", "Water"]
                    transfers = 1
                elif code == "E_ROAD_WATER_VIA_CT":
                    modes = ["Road", "Water"]
                    transfers = 1
                else:
                    modes = ["Road"]
                    transfers = 0

                route_options.append({
                    "code": code,
                    "name": ro.get("ten", code),
                    "cost_vnd": ro.get("chi_phi_du_doan_vnd", 0.0),
                    "duration_hours": ro.get("thoi_gian_du_kien_gio", 0.0),
                    "available": ro.get("trang_thai") == "available",
                    "recommended": code == order.selected_route_id or (code == "B_ROAD_VIA_CT" and not order.selected_route_id),
                    "risk": "low" if code in ["A_DIRECT_ROAD", "B_ROAD_VIA_CT"] else "medium",
                    "modes": modes,
                    "transfers": transfers
                })
        except:
            pass

def calculate_order_progress(order: Any, session: Session) -> float:
    from app.simulation import SYSTEM_CLOCK
    from datetime import datetime, timezone, timedelta
    
    state = order.state
    route_id = order.selected_route_id or "B_ROAD_VIA_CT"
    is_direct = route_id == "A_DIRECT_ROAD"
    
    if state == "created":
        return 0.0
    elif state in ["routed_to_can_tho", "in_transit_to_can_tho"]:
        try:
            start_time = datetime.fromisoformat(order.timestamp)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone(timedelta(hours=7)))
            end_time = datetime.fromisoformat(order.eta_can_tho) if order.eta_can_tho else start_time
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone(timedelta(hours=7)))
            
            total_sec = (end_time - start_time).total_seconds()
            elapsed_sec = (SYSTEM_CLOCK - start_time).total_seconds()
            ratio = max(0.0, min(0.99, elapsed_sec / total_sec if total_sec > 0 else 0.99))
            
            if not is_direct:
                return ratio * 0.50
            return ratio
        except:
            return 0.25 if not is_direct else 0.5
    elif state == "arrived_waiting":
        return 0.50
    elif state == "dispatched":
        from app.models import DispatchOrder
        dispatch = None
        dispatches = session.exec(select(DispatchOrder)).all()
        for d in dispatches:
            shipment_ids = json.loads(d.shipment_ids_json) if d.shipment_ids_json else []
            if order.id in shipment_ids or str(order.id) in shipment_ids:
                dispatch = d
                break
        try:
            if dispatch and dispatch.dispatched_at and dispatch.eta_hcm:
                start_time = datetime.fromisoformat(dispatch.dispatched_at)
                end_time = datetime.fromisoformat(dispatch.eta_hcm)
            else:
                start_time = datetime.fromisoformat(order.dispatched_at) if order.dispatched_at else datetime.now(timezone(timedelta(hours=7)))
                end_time = start_time + timedelta(hours=5)
            
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone(timedelta(hours=7)))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone(timedelta(hours=7)))
                
            total_sec = (end_time - start_time).total_seconds()
            elapsed_sec = (SYSTEM_CLOCK - start_time).total_seconds()
            ratio = max(0.0, min(0.99, elapsed_sec / total_sec if total_sec > 0 else 0.99))
            
            if not is_direct:
                return 0.50 + (ratio * 0.50)
            return ratio
        except:
            return 0.75
    elif state == "delivered":
        return 1.0
    return 0.0

def enrich_order_payload(order: Any, session: Session) -> Dict[str, Any]:
    business_name = get_business_name(order.user_id, session)
    origin = HUB_NAME_MAPPING.get(order.hub_id, order.hub_id)
    destination = "TP. HCM"

    commodity_map = {
        "COM_RICE": "Rice",
        "COM_PANGASIUS": "Seafood",
        "COM_SHRIMP": "Seafood",
        "COM_POMELO": "Fruits",
        "COM_VEGETABLE": "Vegetables",
        "COM_PURPLE_ONION": "Vegetables",
    }
    commodity = commodity_map.get(order.commodity_id, order.loai_hang or "Agri-cargo")

    provider_name = None
    provider_id_str = None
    if order.assigned_vehicle_id:
        from app.models import Vehicle
        veh = session.get(Vehicle, order.assigned_vehicle_id)
        if veh and veh.provider_id:
            provider_id_str = str(veh.provider_id)
            provider_name = get_provider_name(veh.provider_id, session)

    status_map = {
        "created": "awaiting_assignment",
        "routed_to_can_tho": "in_transit",
        "arrived_waiting": "assigned",
        "dispatched": "in_transit",
        "delivered": "delivered",
    }
    status = status_map.get(order.state, order.state)

    route_options = []
    if order.route_options_json:
        try:
            raw_options = json.loads(order.route_options_json)
            for ro in raw_options:
                code = ro.get("route_code", "")
                if code == "A_DIRECT_ROAD":
                    modes = ["Road"]
                    transfers = 0
                elif code == "B_ROAD_VIA_CT":
                    modes = ["Road", "Road"]
                    transfers = 1
                elif code == "C_WATER_ROAD_VIA_CT":
                    modes = ["Water", "Road"]
                    transfers = 1
                elif code == "D_WATER_VIA_CT":
                    modes = ["Water", "Water"]
                    transfers = 1
                elif code == "E_ROAD_WATER_VIA_CT":
                    modes = ["Road", "Water"]
                    transfers = 1
                else:
                    modes = ["Road"]
                    transfers = 0

                route_options.append({
                    "code": code,
                    "name": ro.get("ten", code),
                    "cost_vnd": ro.get("chi_phi_du_doan_vnd", 0.0),
                    "duration_hours": ro.get("thoi_gian_du_kien_gio", 0.0),
                    "available": ro.get("trang_thai") == "available",
                    "recommended": code == order.selected_route_id or (code == "B_ROAD_VIA_CT" and not order.selected_route_id),
                    "risk": "low" if code in ["A_DIRECT_ROAD", "B_ROAD_VIA_CT"] else "medium",
                    "modes": modes,
                    "transfers": transfers
                })
        except:
            pass

    eta_can_tho_fmt = order.eta_can_tho.replace("T", " ").split(".")[0] if order.eta_can_tho else "N/A"
    
    from app.models import DispatchOrder
    dispatch = None
    dispatches = session.exec(select(DispatchOrder)).all()
    for d in dispatches:
        shipment_ids = json.loads(d.shipment_ids_json) if d.shipment_ids_json else []
        if order.id in shipment_ids or str(order.id) in shipment_ids:
            dispatch = d
            break
            
    eta_hcm_fmt = "N/A"
    if dispatch and dispatch.eta_hcm:
        eta_hcm_fmt = dispatch.eta_hcm.replace("T", " ").split(".")[0]
    elif order.dispatched_at:
        try:
            from datetime import datetime, timedelta
            dt = datetime.fromisoformat(order.dispatched_at) + timedelta(hours=5)
            eta_hcm_fmt = dt.isoformat(timespec="seconds").replace("T", " ")
        except:
            pass

    timeline = [
        {"event": "Đơn hàng đã được tạo", "time": order.created_at.replace("T", " ").split(".")[0], "done": True},
        {"event": f"Chọn tuyến & Gán xe vận chuyển ({provider_name or 'Đang chỉ định...'})", "time": order.timestamp.replace("T", " ").split(".")[0] if order.selected_route_id else "Đang chờ chỉ định...", "done": bool(order.selected_route_id)},
        {"event": "Đã tới Can Tho Hub (Gom hàng)", "time": order.actual_arrival_at.replace("T", " ").split(".")[0] if order.actual_arrival_at else (f"Dự kiến tới: {eta_can_tho_fmt}" if order.state in ["routed_to_can_tho", "in_transit_to_can_tho"] else (eta_can_tho_fmt if order.state in ["arrived_waiting", "dispatched", "delivered"] else "Chưa tới")), "done": order.state in ["arrived_waiting", "dispatched", "delivered"]},
        {"event": "Xuất bến di chuyển tới TP.HCM", "time": order.dispatched_at.replace("T", " ").split(".")[0] if order.dispatched_at else (dispatch.dispatched_at.replace("T", " ").split(".")[0] if dispatch and dispatch.dispatched_at else "Chưa xuất bến..."), "done": order.state in ["dispatched", "delivered"]},
        {"event": "Đã giao nhận hàng tại TP.HCM (Hoàn tất)", "time": eta_hcm_fmt if order.state == "delivered" else (f"Dự kiến giao: {eta_hcm_fmt}" if order.state == "dispatched" else "Chưa hoàn tất"), "done": order.state == "delivered"},
    ]

    progress = int(calculate_order_progress(order, session) * 100)

    return {
        "id": f"ORD{order.id:03d}" if order.id else "ORD-NEW",
        "db_id": order.id,
        "business_name": business_name,
        "commodity": commodity,
        "origin": origin,
        "destination": destination,
        "weight_ton": round(order.khoi_luong_kg / 1000.0, 1),
        "deadline": order.delivery_deadline or order.deadline_ts or "N/A",
        "created_at": order.created_at,
        "status": status,
        "estimated_cost_vnd": order.selected_route_cost_vnd or 0.0,
        "recommended_route": order.selected_route_id,
        "provider_id": provider_id_str,
        "provider_name": provider_name,
        "route_options": route_options,
        "timeline": timeline,
        "progress": progress,
    }
