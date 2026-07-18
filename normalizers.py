"""
Mappings verified against:
- data/generated/annual/csv/nodes.csv
- data/generated/annual/compat/dataset_weather.json
- data/generated/annual/compat/dataset_fleet.json
- data/generated/annual/compat/dataset_orders.json
- data/generated/annual/csv/commodities.csv
"""

from __future__ import annotations

import unicodedata


NODE_MAP = {
    "HUB_VITHANH": {
        "slug": "vi_thanh",
        "hub_name_vi": "Hub Vị Thanh",
        "location_label": "Vị Thanh",
    },
    "HUB_LONGXUYEN": {
        "slug": "long_xuyen",
        "hub_name_vi": "Hub Long Xuyên",
        "location_label": "Long Xuyên",
    },
    "HUB_SOCTRANG": {
        "slug": "soc_trang",
        "hub_name_vi": "Hub Sóc Trăng",
        "location_label": "Sóc Trăng",
    },
    "HUB_VINHLONG": {
        "slug": "vinh_long",
        "hub_name_vi": "Hub Vĩnh Long",
        "location_label": "Vĩnh Long",
    },
    "CT_HUB": {
        "slug": "can_tho",
        "hub_name_vi": "Trung tâm trung chuyển Cần Thơ",
        "location_label": "Cần Thơ",
    },
    "HCM_MARKET": {
        "slug": "tp_hcm",
        "hub_name_vi": "Thị trường TP.HCM",
        "location_label": "TP.HCM",
    },
}

SLUG_TO_NODE = {v["slug"]: k for k, v in NODE_MAP.items()}
NAME_TO_NODE = {v["hub_name_vi"]: k for k, v in NODE_MAP.items()}
LOCATION_TO_NODE = {v["location_label"]: k for k, v in NODE_MAP.items()}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    return _strip_accents(value or "").lower().replace(" ", "_").replace("-", "_")


def to_node_id(value: str | None) -> str | None:
    """Map node_id, compat slug, Vietnamese hub name, or location label to canonical node_id."""
    if not value:
        return None
    if value in NODE_MAP:
        return value
    if value in SLUG_TO_NODE:
        return SLUG_TO_NODE[value]
    if value in NAME_TO_NODE:
        return NAME_TO_NODE[value]
    if value in LOCATION_TO_NODE:
        return LOCATION_TO_NODE[value]

    normalized = normalize_text(value)
    for node_id, info in NODE_MAP.items():
        if normalized in {
            normalize_text(node_id),
            normalize_text(info["slug"]),
            normalize_text(info["hub_name_vi"]),
            normalize_text(info["location_label"]),
        }:
            return node_id
    return None


PRIORITY_TIERS = {
    "seafood": {"score": 1.0, "label": "Hải sản"},
    "vegetable": {"score": 0.7, "label": "Rau củ quả"},
    "hard_fruit": {"score": 0.4, "label": "Trái cây cứng"},
    "grain_dry": {"score": 0.1, "label": "Gạo / nông sản khô"},
}

COMMODITY_ID_TO_TIER = {
    "COM_PANGASIUS": "seafood",
    "COM_SHRIMP": "seafood",
    "COM_SWEET_POTATO": "vegetable",
    "COM_PURPLE_ONION": "vegetable",
    "COM_VEGETABLE": "vegetable",
    "COM_POMELO": "hard_fruit",
    "COM_PINEAPPLE": "hard_fruit",
    "COM_ORANGE": "hard_fruit",
    "COM_RICE": "grain_dry",
    "COM_SUGARCANE": "grain_dry",
}

COMMODITY_KEYWORDS = {
    "seafood": [
        "com_pangasius",
        "com_shrimp",
        "ca_tra",
        "ca tra",
        "tom",
        "tôm",
        "shrimp",
        "pangasius",
        "seafood",
        "hai_san",
    ],
    "vegetable": [
        "com_sweet_potato",
        "com_purple_onion",
        "com_vegetable",
        "khoai_lang",
        "khoai lang",
        "hanh_tim",
        "hành tím",
        "rau_mau",
        "rau màu",
        "vegetable",
    ],
    "hard_fruit": [
        "com_pomelo",
        "com_pineapple",
        "com_orange",
        "buoi",
        "bưởi",
        "khom",
        "khóm",
        "cam_sanh",
        "cam sành",
        "fruit",
        "pineapple",
        "pomelo",
        "orange",
    ],
    "grain_dry": [
        "com_rice",
        "com_sugarcane",
        "lua_gao",
        "lúa gạo",
        "gao",
        "gạo",
        "mia",
        "mía",
        "rice",
        "grain",
        "sugarcane",
        "dry",
    ],
}

COMMODITY_LOSS_VALUE = {
    "COM_RICE": {
        "loss_pct_per_hour": 0.010000,
        "value_vnd_per_kg": 16000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t", "barge_200t", "barge_500t"],
    },
    "COM_PANGASIUS": {
        "loss_pct_per_hour": 0.180000,
        "value_vnd_per_kg": 32000.000000,
        "compatible_vehicle_types": ["reefer_8t"],
    },
    "COM_SHRIMP": {
        "loss_pct_per_hour": 0.220000,
        "value_vnd_per_kg": 125000.000000,
        "compatible_vehicle_types": ["reefer_8t"],
    },
    "COM_POMELO": {
        "loss_pct_per_hour": 0.055000,
        "value_vnd_per_kg": 36000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t"],
    },
    "COM_SWEET_POTATO": {
        "loss_pct_per_hour": 0.030000,
        "value_vnd_per_kg": 15000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t"],
    },
    "COM_SUGARCANE": {
        "loss_pct_per_hour": 0.025000,
        "value_vnd_per_kg": 1300.000000,
        "compatible_vehicle_types": ["truck_15t", "boat_50t", "barge_200t", "barge_500t"],
    },
    "COM_PINEAPPLE": {
        "loss_pct_per_hour": 0.060000,
        "value_vnd_per_kg": 10000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t"],
    },
    "COM_PURPLE_ONION": {
        "loss_pct_per_hour": 0.035000,
        "value_vnd_per_kg": 28000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t"],
    },
    "COM_ORANGE": {
        "loss_pct_per_hour": 0.065000,
        "value_vnd_per_kg": 22000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "boat_50t"],
    },
    "COM_VEGETABLE": {
        "loss_pct_per_hour": 0.100000,
        "value_vnd_per_kg": 18000.000000,
        "compatible_vehicle_types": ["truck_5t", "truck_15t", "reefer_8t"],
    },
}

TIER_LOSS_VALUE_FALLBACK = {
    "seafood": {"loss_pct_per_hour": 0.200000, "value_vnd_per_kg": 78500.0},
    "vegetable": {"loss_pct_per_hour": 0.055000, "value_vnd_per_kg": 20333.0},
    "hard_fruit": {"loss_pct_per_hour": 0.060000, "value_vnd_per_kg": 22667.0},
    "grain_dry": {"loss_pct_per_hour": 0.017500, "value_vnd_per_kg": 8650.0},
}


def classify_priority(commodity_id: str | None, loai_hang: str = "") -> dict:
    if commodity_id in COMMODITY_ID_TO_TIER:
        tier = COMMODITY_ID_TO_TIER[commodity_id]
        return {"tier": tier, **PRIORITY_TIERS[tier]}

    text = normalize_text(f"{commodity_id or ''} {loai_hang or ''}")
    for tier, keywords in COMMODITY_KEYWORDS.items():
        normalized_keywords = [normalize_text(keyword) for keyword in keywords]
        if any(keyword in text for keyword in normalized_keywords):
            return {"tier": tier, **PRIORITY_TIERS[tier]}

    fallback = PRIORITY_TIERS["hard_fruit"]
    return {"tier": "hard_fruit", **fallback}


def commodity_loss_value(commodity_id: str | None, loai_hang: str = "") -> dict:
    if commodity_id in COMMODITY_LOSS_VALUE:
        return COMMODITY_LOSS_VALUE[commodity_id]
    priority = classify_priority(commodity_id, loai_hang)
    return TIER_LOSS_VALUE_FALLBACK[priority["tier"]]
