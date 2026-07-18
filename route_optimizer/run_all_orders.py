from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from route_optimizer.data_loader import DEFAULT_DATA_DIR, load_data
from route_optimizer.optimizer import optimize_route


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "all_orders_optimized.csv"
ERRORS_CSV = OUTPUT_DIR / "errors.csv"

ROUTE_CODES = [
    "A_DIRECT_ROAD",
    "B_ROAD_VIA_CT",
    "C_WATER_ROAD_VIA_CT",
    "D_WATER_VIA_CT",
    "E_ROAD_WATER_VIA_CT",
]


def _input_from_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": order["order_id"],
        "hub_id": order["hub_id"],
        "commodity_id": order["commodity_id"],
        "loai_hang": "",
        "khoi_luong_kg": float(order["weight_kg"]),
        "timestamp": order["ready_ts"],
    }


def _empty_row(order_input: dict[str, Any]) -> dict[str, Any]:
    row = {
        "order_id": order_input["order_id"],
        "hub_id": order_input["hub_id"],
        "commodity_id": order_input["commodity_id"],
        "khoi_luong_kg": order_input["khoi_luong_kg"],
        "timestamp": order_input["timestamp"],
        "priority_tier": "",
        "priority_score": "",
        "khuyen_nghi": "",
        "chi_phi_du_doan_vnd": "",
        "thoi_gian_du_kien_gio": "",
    }
    for route_code in ROUTE_CODES:
        row[f"{route_code}_chi_phi_vnd"] = ""
        row[f"{route_code}_trang_thai"] = ""
    return row


def _row_from_result(order_input: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    row = _empty_row(order_input)
    row["priority_tier"] = result["priority"]["tier"]
    row["priority_score"] = result["priority"]["score"]
    row["khuyen_nghi"] = result["recommended_route"] or ""

    by_route = {item["route_code"]: item for item in result["phuong_an"]}
    if result["recommended_route"]:
        winner = by_route[result["recommended_route"]]
        row["chi_phi_du_doan_vnd"] = winner["chi_phi_du_doan_vnd"]
        row["thoi_gian_du_kien_gio"] = winner["thoi_gian_du_kien_gio"]

    for route_code in ROUTE_CODES:
        item = by_route.get(route_code)
        if not item:
            row[f"{route_code}_trang_thai"] = "missing_route"
            continue
        if item["trang_thai"] == "available":
            row[f"{route_code}_chi_phi_vnd"] = item["chi_phi_du_doan_vnd"]
            row[f"{route_code}_trang_thai"] = "available"
        else:
            row[f"{route_code}_chi_phi_vnd"] = ""
            row[f"{route_code}_trang_thai"] = item.get("ly_do") or "currently_unavailable"
    return row


def _fieldnames() -> list[str]:
    fields = [
        "order_id",
        "hub_id",
        "commodity_id",
        "khoi_luong_kg",
        "timestamp",
        "priority_tier",
        "priority_score",
        "khuyen_nghi",
        "chi_phi_du_doan_vnd",
        "thoi_gian_du_kien_gio",
    ]
    for route_code in ROUTE_CODES:
        fields.extend([f"{route_code}_chi_phi_vnd", f"{route_code}_trang_thai"])
    return fields


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    store = load_data(DEFAULT_DATA_DIR)
    rows = []
    errors = []
    recommendation_counts: Counter[str] = Counter()
    ai_total_cost = 0.0
    baseline_a_total_cost = 0.0
    comparable_ai_total_cost = 0.0
    baseline_a_available_count = 0

    for order in store.orders.values():
        order_input = _input_from_order(order)
        try:
            result = optimize_route(order_input)
            output_row = _row_from_result(order_input, result)
            rows.append(output_row)

            selected_route = result["recommended_route"] or "NO_AVAILABLE_ROUTE"
            recommendation_counts[selected_route] += 1
            if output_row["chi_phi_du_doan_vnd"] != "":
                ai_total_cost += float(output_row["chi_phi_du_doan_vnd"])

            route_a = next((item for item in result["phuong_an"] if item["route_code"] == "A_DIRECT_ROAD"), None)
            if route_a and route_a["trang_thai"] == "available" and route_a["chi_phi_du_doan_vnd"] is not None:
                baseline_a_total_cost += float(route_a["chi_phi_du_doan_vnd"])
                baseline_a_available_count += 1
                if output_row["chi_phi_du_doan_vnd"] != "":
                    comparable_ai_total_cost += float(output_row["chi_phi_du_doan_vnd"])
        except Exception as exc:  # noqa: BLE001 - batch job must continue per order
            errors.append({"order_id": order["order_id"], "error": str(exc)})

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_fieldnames())
        writer.writeheader()
        writer.writerows(rows)

    with ERRORS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["order_id", "error"])
        writer.writeheader()
        writer.writerows(errors)

    print(f"Output CSV: {OUTPUT_CSV}")
    print(f"Errors CSV: {ERRORS_CSV}")
    print(f"Processed successfully: {len(rows)}")
    print(f"Errors: {len(errors)}")
    print("Recommendation distribution:")
    for route_code in [*ROUTE_CODES, "NO_AVAILABLE_ROUTE"]:
        print(f"  {route_code}: {recommendation_counts.get(route_code, 0)}")

    print(f"AI recommended total cost VND: {round(ai_total_cost, 2)}")
    print(f"Baseline all A_DIRECT_ROAD total cost VND: {round(baseline_a_total_cost, 2)}")
    print(f"Baseline A_DIRECT_ROAD available orders: {baseline_a_available_count}/{len(store.orders)}")
    if baseline_a_total_cost > 0:
        savings = baseline_a_total_cost - comparable_ai_total_cost
        savings_pct = savings / baseline_a_total_cost * 100
        print(f"Comparable AI cost on A-available orders VND: {round(comparable_ai_total_cost, 2)}")
        print(f"Estimated savings on A-available orders VND: {round(savings, 2)}")
        print(f"Estimated savings on A-available orders percent: {round(savings_pct, 2)}%")


if __name__ == "__main__":
    main()
