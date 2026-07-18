from __future__ import annotations

# Assumptions for this compatibility adapter:
# - Keep optimizer logic unchanged; only emit CSV files with the annual/csv schema.
# - nodes, legs, commodities, and fleet are copied from annual/csv as shared static inputs.
# - fleet availability is moved to 2024-01-01 so the shared fleet exists for the full 3-year span.
# - three_year compat orders lack ids/deadlines/commodity ids, so ids are generated, commodity
#   ids are inferred from priority tier, and deadlines reuse annual average ready-to-deadline
#   gaps by representative commodity.
# - three_year compat weather uses warning buckets, so factors are sampled from matching annual
#   buckets with fixed seed 20260718 for reproducible road/water factor distributions.
# - three_year compat price is treated as a relative fuel index, preserving annual fuel scale.
# - freight_rates.csv and weather_bulletins.csv are intentionally omitted so existing optional
#   loader/fallback behavior remains in charge.

import csv
import json
import random
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from normalizers import classify_priority


ROOT = PROJECT_ROOT / "VAIC_Data_Simulation_Package_v3_2026-07-18"
ANNUAL_CSV = ROOT / "data" / "generated" / "annual" / "csv"
THREE_YEAR = ROOT / "data" / "generated" / "three_year"
THREE_COMPAT = THREE_YEAR / "compat"
OUT_DIR = THREE_YEAR / "csv_adapted"

STATIC_FILES = ["nodes.csv", "legs.csv", "commodities.csv", "fleet.csv"]
FLEET_AVAILABLE_FROM_TS = "2024-01-01T00:00:00+07:00"
WEATHER_SAMPLE_SEED = 20260718
ORDER_COLUMNS = [
    "order_id",
    "hub_id",
    "commodity_id",
    "weight_kg",
    "arrival_ts",
    "ready_ts",
    "deadline_ts",
    "destination_node_id",
    "priority_level",
    "status",
]
WEATHER_COLUMNS = [
    "ts",
    "node_id",
    "rainfall_mm",
    "river_level_m",
    "flood_risk_idx",
    "road_factor",
    "water_factor",
    "alert_level",
]
FUEL_COLUMNS = ["ts", "fuel_type", "price_vnd_per_liter", "adjustment_date", "source_type"]

REPRESENTATIVE_COMMODITY = {
    "seafood": "COM_PANGASIUS",
    "vegetable": "COM_VEGETABLE",
    "hard_fruit": "COM_POMELO",
    "grain_dry": "COM_RICE",
}
PRIORITY_LEVEL = {
    "seafood": "4",
    "vegetable": "3",
    "hard_fruit": "2",
    "grain_dry": "1",
}
WARNING_TO_ALERT = {
    "thap": "none",
    "trung_binh": "watch",
    "cao": "warning",
}
REGION_TO_NODE = {
    "an_giang": "HUB_LONGXUYEN",
    "vinh_long": "HUB_VINHLONG",
    "thanh_pho_ho_chi_minh": "HCM_MARKET",
}
CAN_THO_DUP_NODES = ["CT_HUB", "HUB_SOCTRANG", "HUB_VITHANH"]


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fmt_ts(value: datetime) -> str:
    return value.isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_static_files() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in STATIC_FILES:
        shutil.copy2(ANNUAL_CSV / name, OUT_DIR / name)
    fleet_path = OUT_DIR / "fleet.csv"
    fleet_rows = read_csv(fleet_path)
    for row in fleet_rows:
        row["available_from_ts"] = FLEET_AVAILABLE_FROM_TS
    write_csv(fleet_path, list(fleet_rows[0].keys()), fleet_rows)


def annual_deadline_gaps() -> tuple[dict[str, timedelta], dict[str, timedelta], timedelta]:
    by_commodity: dict[str, list[float]] = defaultdict(list)
    by_tier: dict[str, list[float]] = defaultdict(list)
    all_gaps: list[float] = []
    for row in read_csv(ANNUAL_CSV / "orders.csv"):
        ready = parse_ts(row["ready_ts"])
        deadline = parse_ts(row["deadline_ts"])
        gap = (deadline - ready).total_seconds()
        commodity_id = row["commodity_id"]
        tier = classify_priority(commodity_id, "")["tier"]
        by_commodity[commodity_id].append(gap)
        by_tier[tier].append(gap)
        all_gaps.append(gap)

    commodity_avg = {k: timedelta(seconds=mean(v)) for k, v in by_commodity.items()}
    tier_avg = {k: timedelta(seconds=mean(v)) for k, v in by_tier.items()}
    fallback = timedelta(seconds=mean(all_gaps)) if all_gaps else timedelta(hours=24)
    return commodity_avg, tier_avg, fallback


def adapt_orders() -> None:
    commodity_avg, tier_avg, fallback_gap = annual_deadline_gaps()
    with (THREE_COMPAT / "dataset_orders.json").open(encoding="utf-8") as f:
        source = json.load(f)

    rows = []
    for index, item in enumerate(source, start=1):
        tier = classify_priority(None, item.get("loai_hang", ""))["tier"]
        commodity_id = REPRESENTATIVE_COMMODITY[tier]
        ready = parse_ts(item["timestamp"])
        gap = commodity_avg.get(commodity_id) or tier_avg.get(tier) or fallback_gap
        rows.append(
            {
                "order_id": f"ORD_3Y_{index:06d}",
                "hub_id": item["hub_id"],
                "commodity_id": commodity_id,
                "weight_kg": f"{float(item['khoi_luong_kg']):.6f}",
                "arrival_ts": fmt_ts(ready),
                "ready_ts": fmt_ts(ready),
                "deadline_ts": fmt_ts(ready + gap),
                "destination_node_id": "HCM_MARKET",
                "priority_level": PRIORITY_LEVEL[tier],
                "status": "new",
            }
        )
    write_csv(OUT_DIR / "orders.csv", ORDER_COLUMNS, rows)


def annual_weather_buckets() -> dict[str, dict[str, list[float]]]:
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in read_csv(ANNUAL_CSV / "weather.csv"):
        bucket = row["alert_level"]
        buckets[bucket]["rainfall_mm"].append(float(row["rainfall_mm"]))
        if row["river_level_m"]:
            buckets[bucket]["river_level_m"].append(float(row["river_level_m"]))
        buckets[bucket]["flood_risk_idx"].append(float(row["flood_risk_idx"]))
        buckets[bucket]["road_factor"].append(float(row["road_factor"]))
        buckets[bucket]["water_factor"].append(float(row["water_factor"]))
    return buckets


def adapt_weather() -> None:
    bucket_values = annual_weather_buckets()
    default_values = bucket_values.get("none") or next(iter(bucket_values.values()))
    rng = random.Random(WEATHER_SAMPLE_SEED)
    with (THREE_COMPAT / "dataset_weather.json").open(encoding="utf-8") as f:
        source = json.load(f)

    can_tho_seen_by_ts: dict[str, int] = defaultdict(int)
    rows = []
    for item in source:
        region = item["region"]
        if region == "can_tho":
            seen = can_tho_seen_by_ts[item["timestamp"]]
            node_id = CAN_THO_DUP_NODES[seen % len(CAN_THO_DUP_NODES)]
            can_tho_seen_by_ts[item["timestamp"]] += 1
        else:
            node_id = REGION_TO_NODE.get(region)
        if not node_id:
            continue

        alert = WARNING_TO_ALERT.get(item.get("canh_bao_mua_lu"), "none")
        values = bucket_values.get(alert) or default_values
        river_level_cm = item.get("muc_nuoc_song_cm")
        river_level_m = "" if river_level_cm is None else f"{float(river_level_cm) / 100:.6f}"
        rows.append(
            {
                "ts": item["timestamp"],
                "node_id": node_id,
                "rainfall_mm": f"{rng.choice(values.get('rainfall_mm') or [0.0]):.6f}",
                "river_level_m": river_level_m,
                "flood_risk_idx": f"{rng.choice(values.get('flood_risk_idx') or [0.0]):.6f}",
                "road_factor": f"{rng.choice(values.get('road_factor') or [1.0]):.6f}",
                "water_factor": f"{rng.choice(values.get('water_factor') or [1.0]):.6f}",
                "alert_level": alert,
            }
        )
    write_csv(OUT_DIR / "weather.csv", WEATHER_COLUMNS, rows)


def annual_fuel_baseline() -> dict[str, float]:
    baseline: dict[str, float] = {}
    for row in read_csv(ANNUAL_CSV / "fuel_prices.csv"):
        baseline.setdefault(row["fuel_type"], float(row["price_vnd_per_liter"]))
    return baseline


def adapt_fuel_prices() -> None:
    baseline = annual_fuel_baseline()
    with (THREE_COMPAT / "dataset_price.json").open(encoding="utf-8") as f:
        source = json.load(f)
    if not source:
        write_csv(OUT_DIR / "fuel_prices.csv", FUEL_COLUMNS, [])
        return

    compat_baseline = float(source[0]["gia_nhien_lieu_per_km"]) or 1.0
    rows = []
    for item in source:
        ratio = float(item["gia_nhien_lieu_per_km"]) / compat_baseline
        adjustment_date = item["timestamp"][:10]
        for fuel_type, base_price in baseline.items():
            rows.append(
                {
                    "ts": item["timestamp"],
                    "fuel_type": fuel_type,
                    "price_vnd_per_liter": f"{base_price * ratio:.6f}",
                    "adjustment_date": adjustment_date,
                    "source_type": "three_year_compat_adapted",
                }
            )
    write_csv(OUT_DIR / "fuel_prices.csv", FUEL_COLUMNS, rows)


def main() -> None:
    copy_static_files()
    adapt_orders()
    adapt_weather()
    adapt_fuel_prices()
    print(f"Adapted CSV data written to: {OUT_DIR}")
    for name in [
        "nodes.csv",
        "legs.csv",
        "commodities.csv",
        "fleet.csv",
        "orders.csv",
        "weather.csv",
        "fuel_prices.csv",
    ]:
        rows = read_csv(OUT_DIR / name)
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
