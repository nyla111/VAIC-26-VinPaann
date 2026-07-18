from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from route_optimizer.optimizer import optimize_route


DEFAULT_DATA_DIR = Path(
    os.getenv(
        "VAIC_DATA_DIR",
        PROJECT_ROOT / "VAIC_Data_Simulation_Package_v3_2026-07-18" / "data" / "generated" / "annual" / "csv",
    )
)


def run_optimizer(input_data: dict[str, Any], data_dir: str | Path | None = None) -> dict[str, Any]:
    return optimize_route(input_data, data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR)
