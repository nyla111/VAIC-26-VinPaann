#!/usr/bin/env python3
"""Multi-seed robustness audit without materializing full freight packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import generate_data as generator


def one_run(config_path: Path, seed: int) -> dict[str, object]:
    config = generator.load_config(config_path)
    config["dataset"]["seed"] = int(seed)
    nodes = generator.build_nodes(config)
    weather = generator.generate_weather(config, nodes)
    orders = generator.generate_orders(config, weather)
    orders["_time"] = pd.to_datetime(orders["arrival_ts"])
    orders["month"] = orders["_time"].dt.strftime("%Y-%m")
    orders["year"] = orders["_time"].dt.year
    monthly = orders.groupby("month")["weight_kg"].sum() / 1000.0
    annual = orders.groupby("year")["weight_kg"].sum() / 1000.0
    actual_index = annual / float(annual.loc[2024])
    target = {
        int(year): float(value)
        for year, value in config["temporal_generation"]["annual_demand_index"].items()
    }
    relative_error = {
        str(year): float(abs(actual_index.loc[year] - target[year]) / target[year])
        for year in target
    }
    return {
        "seed": int(seed),
        "orders": int(len(orders)),
        "monthly_peak_trough": float(monthly.max() / monthly.min()),
        "lag12_autocorrelation": float(monthly.autocorr(lag=12)),
        "actual_annual_index": {
            str(year): float(value) for year, value in actual_index.items()
        },
        "annual_relative_error": relative_error,
        "resolved_temporal_effects": config.get("_resolved", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base_3y.yaml")
    parser.add_argument("--output", default="reports/quality_three_year_multiseed_v4.json")
    args = parser.parse_args()
    config_path = Path(args.config)
    base = generator.load_config(config_path)
    base_seed = int(base["dataset"]["seed"])
    seeds = [base_seed + offset for offset in (0, 997, 1994)]
    runs = [one_run(config_path, seed) for seed in seeds]
    guardrails = base["validation"]["temporal_guardrails"]
    checks = {
        "all_peak_trough_in_range": all(
            float(guardrails["monthly_peak_trough"]["min"])
            <= float(run["monthly_peak_trough"])
            <= float(guardrails["monthly_peak_trough"]["max"])
            for run in runs
        ),
        "all_lag12_positive": all(
            float(run["lag12_autocorrelation"])
            >= float(guardrails["lag12_autocorrelation_min"])
            for run in runs
        ),
        "all_annual_indices_within_tolerance": all(
            max(float(value) for value in run["annual_relative_error"].values())
            <= float(guardrails["annual_index_relative_error_max"])
            for run in runs
        ),
        "seed_changes_outputs": len({int(run["orders"]) for run in runs}) > 1,
    }
    checks = {name: bool(value) for name, value in checks.items()}
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "seeds": seeds,
        "runs": runs,
        "checks": checks,
        "checks_passed": int(sum(checks.values())),
        "checks_failed": int(len(checks) - sum(checks.values())),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

