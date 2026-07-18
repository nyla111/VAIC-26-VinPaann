from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ai.route_optimizer.data_loader import load_data
from app.ai.route_optimizer.optimizer import optimize_route



ROOT = Path(__file__).resolve().parent / "VAIC_Data_Simulation_Package_v3_2026-07-18"
GENERATED = ROOT / "data" / "generated"
REFERENCE = ROOT / "eval" / "reference_routes.csv"
REPORT = Path(__file__).resolve().parent / "reference_mismatch_classification.json"

REFERENCE_ROUTE_ALIASES = {
    "C_WATER_VIA_CT": "D_WATER_VIA_CT",
}


def scenario_data_dir(pack: str) -> Path:
    if pack == "annual":
        return GENERATED / "annual" / "csv"
    return GENERATED / "scenarios" / pack / "csv"


def route_direction(route_code: str | None) -> str:
    if not route_code or route_code == "INFEASIBLE":
        return "infeasible"
    if route_code == "A_DIRECT_ROAD":
        return "direct"
    return "via_ct"


def main() -> None:
    total = 0
    matched = 0
    group_1_acceptable = []
    group_2_serious = []

    orders_cache = {}
    with REFERENCE.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            data_dir = scenario_data_dir(row["pack"])
            store = load_data(data_dir)
            orders = store.orders
            if not orders:
                if data_dir not in orders_cache:
                    orders_path = data_dir / "orders.csv"
                    if orders_path.exists():
                        with orders_path.open(encoding="utf-8-sig", newline="") as f_ord:
                            orders_cache[data_dir] = {r["order_id"]: r for r in csv.DictReader(f_ord)}
                    else:
                        orders_cache[data_dir] = {}
                orders = orders_cache[data_dir]
            order = orders[row["order_id"]]
            input_data = {
                "order_id": row["order_id"],
                "hub_id": order["hub_id"],
                "commodity_id": order["commodity_id"],
                "loai_hang": "",
                "khoi_luong_kg": float(order["weight_kg"]),
                "timestamp": row["decision_ts"],
            }
            result = optimize_route(input_data, data_dir=data_dir)

            expected = REFERENCE_ROUTE_ALIASES.get(row["reference_route"], row["reference_route"])
            actual = result["recommended_route"] or "INFEASIBLE"
            if actual == expected:
                matched += 1
            else:
                item = {
                    "eval_id": row["eval_id"],
                    "pack": row["pack"],
                    "order_id": row["order_id"],
                    "input": input_data,
                    "optimizer_recommended_route": actual,
                    "optimizer_khuyen_nghi": result["khuyen_nghi"],
                    "reference_route": expected,
                    "raw_reference_route": row["reference_route"],
                    "optimizer_direction": route_direction(actual),
                    "reference_direction": route_direction(expected),
                    "reference_rationale_codes": row["rationale_codes"],
                    "reference_feasible_routes": row["feasible_routes"],
                    "reference_infeasible_routes": row["infeasible_routes"],
                    "reference_route_a_cost_vnd": row["route_a_cost_vnd"],
                    "reference_route_b_cost_vnd": row["route_b_cost_vnd"],
                    "reference_route_c_cost_vnd": row["route_c_cost_vnd"],
                    "reference_total_cost_vnd": row["reference_total_cost_vnd"],
                    "reference_elapsed_hr": row["reference_elapsed_hr"],
                    "optimizer_phuong_an": result["phuong_an"],
                    "optimizer_evidence": result["evidence"],
                }
                if item["optimizer_direction"] == item["reference_direction"] == "via_ct":
                    item["classification"] = "group_1_acceptable_model_change"
                    group_1_acceptable.append(item)
                else:
                    item["classification"] = "group_2_serious_direction_change"
                    group_2_serious.append(item)

    report = {
        "summary": {
            "total_cases": total,
            "exact_or_legacy_alias_matched": matched,
            "mismatches": len(group_1_acceptable) + len(group_2_serious),
            "group_1_acceptable_model_change": len(group_1_acceptable),
            "group_2_serious_direction_change": len(group_2_serious),
        },
        "group_1_acceptable_model_change": group_1_acceptable,
        "group_2_serious_direction_change": group_2_serious,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    pct = matched / total * 100 if total else 0
    print(f"Matched {matched}/{total} = {pct:.2f}%")
    print("Classification:")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Full report written to: {REPORT}")
    if group_2_serious:
        print("Group 2 serious eval_ids:")
        print(", ".join(item["eval_id"] for item in group_2_serious))


if __name__ == "__main__":
    main()
