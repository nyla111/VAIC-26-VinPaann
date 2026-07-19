"""Precompute + cache "shipment thật đi qua Cần Thơ" ra JSON, để endpoint what-if live
demo không phải chờ (thời gian `load_ct_bound_shipments()` quét order + gọi
`optimize_route()` của AI1)

Chạy:
    cd VAIC-26-VinPaann
    python -m ai2_dispatch.scripts.cache_shipments
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ai2_dispatch.scripts.simulate_and_tune import load_ct_bound_shipments

CACHE_PATH = Path(__file__).resolve().parents[1] / "reports" / "ct_bound_shipments_cache.json"


def main() -> None:
    print("Loading Cần Thơ-bound shipments from real orders.csv via AI1 optimize_route()...")
    shipments = load_ct_bound_shipments()
    print(f"  {len(shipments)} shipments cached.")

    rows = []
    for s in shipments:
        row = asdict(s)
        row["outbound_mode"] = s.outbound_mode.value
        row["created_at"] = s.created_at.isoformat()
        row["eta_can_tho"] = s.eta_can_tho.isoformat()
        rows.append(row)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cached to {CACHE_PATH}")


if __name__ == "__main__":
    main()
