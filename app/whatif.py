"""Live "what-if" scenario simulation — dùng cho demo/Q&A trực tiếp thay vì slide tĩnh.

Đọc shipment thật đã cache sẵn (`scripts/cache_shipments.py`, ~150 shipment "đi qua Cần Thơ"
lấy từ orders.csv canonical qua đúng `optimize_route()` của AI1),
áp perturbation đơn giản (trễ do thời tiết, giảm fleet, tăng/giảm nhu cầu), rồi chạy lại
`simulate_and_tune.run_simulation()` để so sánh baseline vs kịch bản ngay lập tức.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import decision_engine
from .data_loader import DEFAULT_DATA_DIR as AI2_DATA_DIR
from .enums import Mode, VehicleStatus
from .state_store import StateStore

CACHE_PATH = Path(__file__).resolve().parents[1] / "reports" / "ct_bound_shipments_cache.json"


@lru_cache(maxsize=1)
def load_cached_shipments():
    from ..scripts.simulate_and_tune import SimShipment  # local import: avoid import cycle at module load

    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"Chưa có cache shipment tại {CACHE_PATH}. Chạy trước: "
            "python -m ai2_dispatch.scripts.cache_shipments"
        )
    rows = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return tuple(
        SimShipment(
            shipment_id=row["shipment_id"],
            hub_id=row["hub_id"],
            commodity_id=row["commodity_id"],
            weight_kg=row["weight_kg"],
            selected_route=row["selected_route"],
            outbound_mode=Mode(row["outbound_mode"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            eta_can_tho=datetime.fromisoformat(row["eta_can_tho"]),
        )
        for row in rows
    )


@dataclass(frozen=True)
class WhatIfScenario:
    weather_delay_multiplier: float = 1.0
    demand_multiplier: float = 1.0
    fleet_vehicles_removed: int = 0
    label: str = "custom"


def apply_scenario(shipments, scenario: WhatIfScenario) -> list:
    adjusted = []
    for s in shipments:
        inbound_hours = max((s.eta_can_tho - s.created_at).total_seconds() / 3600.0, 0.0)
        new_inbound_hours = inbound_hours * scenario.weather_delay_multiplier
        new_eta = s.created_at + timedelta(hours=new_inbound_hours)
        adjusted.append(
            replace(s, eta_can_tho=new_eta, weight_kg=s.weight_kg * scenario.demand_multiplier)
        )
    return adjusted


def _remove_vehicles(store: StateStore, count: int) -> None:
    if count <= 0:
        return
    candidates = sorted(
        (v for v in store.vehicles.values() if v.status == VehicleStatus.AVAILABLE),
        key=lambda v: v.capacity_kg,
    )
    for vehicle in candidates[:count]:
        vehicle.status = VehicleStatus.MAINTENANCE


@lru_cache(maxsize=4)
def _baseline_metrics(config: decision_engine.DecisionConfig):
    import ai2_dispatch.scripts.simulate_and_tune as sim_module

    shipments = apply_scenario(load_cached_shipments(), PRESET_SCENARIOS["baseline"])
    return sim_module.run_simulation(shipments, config, ai2_data_dir=AI2_DATA_DIR)


def run_scenario(scenario: WhatIfScenario, config: Optional[decision_engine.DecisionConfig] = None):
    """Trả về `SimMetrics` (xem scripts/simulate_and_tune.py). `fleet_vehicles_removed` cần
    can thiệp vào bước bootstrap fleet của MỌI StateStore được tạo trong lúc chạy (mỗi
    tháng trong sample là 1 episode/StateStore riêng — xem `run_simulation`), nên tạm patch
    `StateStore._bootstrap_fleet` trong lúc chạy rồi khôi phục ngay (try/finally) — service
    live vẫn dùng đúng 1 StateStore singleton tạo từ trước lúc import, không bị ảnh hưởng."""

    import ai2_dispatch.scripts.simulate_and_tune as sim_module

    config = config or decision_engine.DecisionConfig()
    shipments = apply_scenario(load_cached_shipments(), scenario)

    if scenario.fleet_vehicles_removed <= 0:
        return sim_module.run_simulation(shipments, config, ai2_data_dir=AI2_DATA_DIR)

    original_bootstrap = StateStore._bootstrap_fleet

    def _patched_bootstrap(self: StateStore, data_dir) -> None:
        original_bootstrap(self, data_dir)
        _remove_vehicles(self, scenario.fleet_vehicles_removed)

    StateStore._bootstrap_fleet = _patched_bootstrap
    try:
        return sim_module.run_simulation(shipments, config, ai2_data_dir=AI2_DATA_DIR)
    finally:
        StateStore._bootstrap_fleet = original_bootstrap


PRESET_SCENARIOS = {
    "baseline": WhatIfScenario(label="baseline (data thật, không perturb)"),
    "flood": WhatIfScenario(weather_delay_multiplier=1.8, label="lũ kiểu S2: +80% thời gian di chuyển hub->Cần Thơ"),
    "fleet_loss": WhatIfScenario(fleet_vehicles_removed=5, label="mất 5 xe/phương tiện nhỏ nhất tại Cần Thơ"),
    "demand_surge": WhatIfScenario(demand_multiplier=1.5, label="nhu cầu tăng 50%"),
    "flood_and_fleet_loss": WhatIfScenario(
        weather_delay_multiplier=1.8, fleet_vehicles_removed=5, label="lũ + mất 5 xe cùng lúc"
    ),
}
