#!/usr/bin/env python3
"""Acceptance audit for temporal coverage, seasonality, trend, geography and leakage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import generate_data as generator


def audit(config_path: Path, pack_dir: Path) -> dict[str, Any]:
    config = generator.load_config(config_path)
    csv_dir = pack_dir / "csv"
    analytics_dir = pack_dir / config["analytics"]["directory_name"]
    orders = pd.read_csv(csv_dir / "orders.csv")
    weather = pd.read_csv(csv_dir / "weather.csv")
    monthly = pd.read_csv(analytics_dir / config["analytics"]["monthly_trends_filename"])
    impacts = pd.read_csv(analytics_dir / config["analytics"]["weather_impacts_filename"])
    metadata = json.loads((pack_dir / "metadata.json").read_text(encoding="utf-8"))

    order_time = pd.to_datetime(orders["arrival_ts"])
    weather_time = pd.to_datetime(weather["ts"])
    order_months = sorted(order_time.dt.strftime("%Y-%m").unique())
    weather_months = sorted(weather_time.dt.strftime("%Y-%m").unique())
    order_year = order_time.dt.year
    id_year = orders["order_id"].str.extract(r"^ORD_(\d{4})_")[0].astype(int)

    monthly_total = monthly.groupby("month", sort=True)["total_weight_tons"].sum()
    annual_total = monthly.assign(year=monthly["month"].str[:4].astype(int)).groupby("year")["total_weight_tons"].sum()
    actual_index = annual_total / float(annual_total.loc[2024])
    target_index = {
        int(year): float(value)
        for year, value in config["temporal_generation"]["annual_demand_index"].items()
    }
    annual_relative_error = {
        str(year): float(abs(actual_index.loc[year] - target) / target)
        for year, target in target_index.items()
    }

    month_matrix = monthly_total.rename("tons").reset_index()
    month_matrix["year"] = month_matrix["month"].str[:4].astype(int)
    month_matrix["month_number"] = month_matrix["month"].str[-2:].astype(int)
    pivot = month_matrix.pivot(index="month_number", columns="year", values="tons")
    pair_correlations = [
        float(pivot[left].corr(pivot[right]))
        for left, right in ((2024, 2025), (2024, 2026), (2025, 2026))
    ]
    lag12 = float(monthly_total.autocorr(lag=12))
    peak_trough = float(monthly_total.max() / monthly_total.min())

    july_2025 = float(monthly_total.loc["2025-07"])
    comparison_july = float(
        (
            monthly_total.loc["2024-07"] * target_index[2025] / target_index[2024]
            + monthly_total.loc["2026-07"] * target_index[2025] / target_index[2026]
        )
        / 2.0
    )
    july_ratio = july_2025 / comparison_july

    daily_orders = orders.assign(date=order_time.dt.strftime("%Y-%m-%d")).groupby(["date", "hub_id"]).size().rename("orders")
    impact_index = impacts.set_index(["date", "hub_id"])
    joined = impact_index.join(daily_orders, how="left").fillna({"orders": 0})
    adverse_correlation = float((1.0 - joined["supply_factor"]).corr(joined["orders"]))

    expected_weather_rows = len(pd.date_range(config["dataset"]["start"], config["dataset"]["end"], freq="h")) * len(pd.read_csv(csv_dir / "nodes.csv"))
    commodity_coverage = monthly.groupby("commodity_id")["month"].nunique().to_dict()
    hub_year_coverage = orders.assign(year=order_year).groupby("hub_id")["year"].nunique().to_dict()
    guardrails = config["validation"]["temporal_guardrails"]
    geography_versions = sorted(monthly["admin_version"].dropna().unique())
    old_admin_names = {"Hậu Giang", "Sóc Trăng", "Bến Tre", "Long An", "Kiên Giang", "Bạc Liêu", "Tiền Giang"}
    compat_weather = pd.read_json(pack_dir / "compat" / "dataset_weather.json")
    expected_compat_regions = {
        "an_giang",
        "can_tho",
        "thanh_pho_ho_chi_minh",
        "vinh_long",
    }

    checks = {
        "orders_cover_36_months": len(order_months) == int(guardrails["expected_months"]),
        "weather_covers_36_months": len(weather_months) == int(guardrails["expected_months"]),
        "weather_has_no_missing_hours": len(weather) == expected_weather_rows,
        "timestamps_use_plus_07": orders["arrival_ts"].str.endswith("+07:00").all() and weather["ts"].str.endswith("+07:00").all(),
        "every_hub_has_three_years": min(hub_year_coverage.values()) == 3,
        "order_id_year_matches_timestamp": bool((id_year.to_numpy() == order_year.to_numpy()).all()),
        "commodity_month_coverage": min(commodity_coverage.values()) >= int(guardrails["commodity_month_coverage_min"]),
        "monthly_peak_trough_guardrail": float(guardrails["monthly_peak_trough"]["min"]) <= peak_trough <= float(guardrails["monthly_peak_trough"]["max"]),
        "positive_lag12_autocorrelation": lag12 >= float(guardrails["lag12_autocorrelation_min"]),
        "same_month_patterns_repeat_but_differ": min(pair_correlations) >= float(guardrails["same_month_year_correlation_min"]) and not np.allclose(pivot[2024], pivot[2025]),
        "annual_index_within_tolerance": max(annual_relative_error.values()) <= float(guardrails["annual_index_relative_error_max"]),
        "no_july_2025_artificial_jump": float(guardrails["july_2025_neighbor_ratio"]["min"]) <= july_ratio <= float(guardrails["july_2025_neighbor_ratio"]["max"]),
        "post_merger_geography_is_consistent": geography_versions == ["harmonized_post_2025"] and not bool(old_admin_names.intersection(set(monthly["admin_name"]))) and set(compat_weather["region"]) == expected_compat_regions,
        "weather_order_relation_is_not_perfect": np.isfinite(adverse_correlation) and abs(adverse_correlation) < 0.80,
        "resolved_year_effects_are_recorded": set(metadata["resolved_temporal_effects"]["demand_year_noise"]) == {"2024", "2025", "2026"} and set(metadata["resolved_temporal_effects"]["year_weather_anomaly"]) == {"2024", "2025", "2026"},
    }
    checks = {name: bool(value) for name, value in checks.items()}
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "dataset_version": metadata["dataset_version"],
        "period": metadata["period"],
        "row_counts": metadata["row_counts"],
        "metrics": {
            "order_months": len(order_months),
            "weather_months": len(weather_months),
            "monthly_peak_trough": round(peak_trough, 6),
            "lag12_autocorrelation": round(lag12, 6),
            "same_month_year_correlations": [round(value, 6) for value in pair_correlations],
            "annual_tonnage": {str(year): round(float(value), 6) for year, value in annual_total.items()},
            "actual_annual_index": {str(year): round(float(value), 6) for year, value in actual_index.items()},
            "target_annual_index": {str(year): value for year, value in target_index.items()},
            "annual_relative_error": {year: round(value, 6) for year, value in annual_relative_error.items()},
            "july_2025_comparable_ratio": round(july_ratio, 6),
            "weather_order_adverse_correlation": round(adverse_correlation, 6),
            "commodity_month_coverage": {str(key): int(value) for key, value in commodity_coverage.items()},
            "hub_year_coverage": {str(key): int(value) for key, value in hub_year_coverage.items()},
            "resolved_temporal_effects": metadata["resolved_temporal_effects"],
        },
        "checks_passed": int(sum(checks.values())),
        "checks_failed": int(len(checks) - sum(checks.values())),
        "checks": checks,
        "assumptions": [
            "Annual growth, production/market seasonality and weather coefficients are synthetic assumptions.",
            "All 2024-2026 records use post-2025 harmonized province/city names by user request.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base_3y.yaml")
    parser.add_argument("--pack-dir", default="data/generated/three_year")
    parser.add_argument("--output", default="reports/quality_three_year_v4.json")
    args = parser.parse_args()
    result = audit(Path(args.config), Path(args.pack_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": result["checks_passed"], "failed": result["checks_failed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
