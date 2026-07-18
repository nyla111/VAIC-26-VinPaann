#!/usr/bin/env python3
"""Audit decision signal and generalization risk in VAIC synthetic data.

The audit deliberately reports ranges across several seeds when requested.  It
is not a generator acceptance oracle tied to one checked-in sample.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import generate_data as generator  # noqa: E402


def _safe_float(value: float) -> float | None:
    return round(float(value), 6) if math.isfinite(float(value)) else None


def order_signal_metrics(orders: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    frame = orders.copy()
    frame["arrival_ts"] = pd.to_datetime(frame["arrival_ts"])
    frame["date"] = frame["arrival_ts"].dt.floor("D")
    frame["hour"] = frame["arrival_ts"].dt.floor("h")
    frame["month"] = frame["arrival_ts"].dt.month
    frame["dow"] = frame["arrival_ts"].dt.dayofweek

    hubs = sorted(config["order_generation"]["hubs"])
    start = pd.Timestamp(config["dataset"]["start"]).floor("D")
    end = pd.Timestamp(config["dataset"]["end"]).floor("D")
    days = pd.date_range(start, end, freq="D")
    daily_grid = pd.MultiIndex.from_product([days, hubs], names=["date", "hub_id"])
    daily = (
        frame.groupby(["date", "hub_id"]).size().reindex(daily_grid, fill_value=0).rename("orders").reset_index()
    )
    daily["month"] = daily["date"].dt.month
    daily["dow"] = daily["date"].dt.dayofweek

    group_mean = daily.groupby(["hub_id", "month", "dow"])["orders"].transform("mean")
    residual = float(np.square(daily["orders"] - group_mean).sum())
    total = float(np.square(daily["orders"] - daily["orders"].mean()).sum())
    calendar_r2 = 1.0 - residual / total if total > 0 else math.nan

    variance_mean = daily.groupby("hub_id")["orders"].agg(["mean", "var"])
    variance_mean["ratio"] = variance_mean["var"] / variance_mean["mean"]

    hours = pd.date_range(
        pd.Timestamp(config["dataset"]["start"]).floor("h"),
        pd.Timestamp(config["dataset"]["end"]).floor("h"),
        freq="h",
    )
    hourly_grid = pd.MultiIndex.from_product([hours, hubs], names=["hour", "hub_id"])
    hourly = frame.groupby(["hour", "hub_id"]).size().reindex(hourly_grid, fill_value=0)

    monthly_ton = frame.groupby("month")["weight_kg"].sum() / 1000.0
    peak_trough = float(monthly_ton.max() / monthly_ton.min()) if monthly_ton.min() > 0 else math.nan

    commodities = pd.DataFrame(config["commodities"])[["commodity_id", "water_ok"]]
    water = frame.merge(commodities, on="commodity_id", how="left", validate="many_to_one")
    water_daily = (
        water.loc[water["water_ok"].fillna(False)]
        .groupby(["date", "hub_id"])["weight_kg"]
        .sum()
        .div(1000.0)
        .reindex(daily_grid, fill_value=0.0)
        .groupby("hub_id")
        .median()
    )

    return {
        "rows": int(len(frame)),
        "daily_orders_per_hub_mean": _safe_float(daily["orders"].mean()),
        "daily_variance_mean_ratio": _safe_float(variance_mean["ratio"].mean()),
        "calendar_oracle_r2_hub_month_dow": _safe_float(calendar_r2),
        "monthly_tonnage_peak_trough": _safe_float(peak_trough),
        "hourly_zero_share": _safe_float((hourly == 0).mean()),
        "median_water_eligible_ton_per_day_by_hub": {
            str(key): _safe_float(value) for key, value in water_daily.items()
        },
    }


def route_geometry(legs: pd.DataFrame, hubs: list[str]) -> dict[str, Any]:
    lookup = {
        (row.from_node_id, row.to_node_id, row.mode): float(row.distance_km)
        for row in legs.itertuples(index=False)
    }
    rows: dict[str, Any] = {}
    ct_hcm = lookup.get(("CT_HUB", "HCM_MARKET", "road"))
    for hub in hubs:
        direct = lookup.get((hub, "HCM_MARKET", "road"))
        to_ct = lookup.get((hub, "CT_HUB", "road"))
        via = to_ct + ct_hcm if to_ct is not None and ct_hcm is not None else None
        rows[hub] = {
            "direct_road_km": _safe_float(direct) if direct is not None else None,
            "via_ct_road_km": _safe_float(via) if via is not None else None,
            "via_ct_detour_pct": (
                _safe_float((via / direct - 1.0) * 100.0)
                if direct and via is not None
                else None
            ),
        }
    return rows


def audit_pack(root: Path, config_path: Path) -> dict[str, Any]:
    config = generator.load_config(config_path)
    annual = root / "annual"
    orders = pd.read_csv(annual / "csv" / "orders.csv")
    legs = pd.read_csv(annual / "csv" / "legs.csv")
    fleet = pd.read_csv(annual / "csv" / "fleet.csv")
    metadata = json.loads((annual / "metadata.json").read_text(encoding="utf-8"))
    grounding_counts = {}
    for table in ("weather_bulletins", "ops_notes", "policy_docs"):
        path = annual / "csv" / f"{table}.csv"
        grounding_counts[table] = int(len(pd.read_csv(path))) if path.is_file() else 0

    eval_path = ROOT / "eval" / "reference_routes.csv"
    freight_path = annual / "csv" / "freight_rates.csv"
    freight_columns = pd.read_csv(freight_path, nrows=0).columns.tolist()
    return {
        "dataset_version": metadata.get("dataset_version"),
        "orders": order_signal_metrics(orders, config),
        "route_geometry": route_geometry(
            legs, list(config["validation"]["required_hubs"])
        ),
        "barge_locations": (
            fleet.loc[fleet["vehicle_type"].isin(["barge_200t", "barge_500t"])]
            .groupby(["vehicle_type", "current_node_id"])
            .size()
            .rename("vehicles")
            .reset_index()
            .to_dict(orient="records")
        ),
        "fuel_freight_linkage_columns_present": all(
            column in freight_columns
            for column in ("fuel_type", "fuel_price_vnd_per_liter", "fuel_cost_factor")
        ),
        "grounding_row_counts": grounding_counts,
        "evaluation_rows": int(len(pd.read_csv(eval_path))) if eval_path.is_file() else 0,
    }


def multi_seed_metrics(config_path: Path, seeds: list[int]) -> dict[str, Any]:
    metrics = []
    for seed in seeds:
        config = generator.load_config(config_path)
        config["dataset"]["seed"] = seed
        orders = generator.generate_orders(config)
        row = order_signal_metrics(orders, config)
        row["seed"] = seed
        metrics.append(row)

    tracked = (
        "rows",
        "daily_variance_mean_ratio",
        "calendar_oracle_r2_hub_month_dow",
        "monthly_tonnage_peak_trough",
        "hourly_zero_share",
    )
    summary: dict[str, Any] = {}
    for key in tracked:
        values = np.asarray([float(row[key]) for row in metrics], dtype=float)
        summary[key] = {
            "min": _safe_float(values.min()),
            "median": _safe_float(np.median(values)),
            "max": _safe_float(values.max()),
        }
    return {"seeds": seeds, "summary": summary, "runs": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "base.yaml")
    parser.add_argument("--multi-seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = audit_pack(args.root.resolve(), args.config.resolve())
    if args.multi_seed:
        base_seed = int(generator.load_config(args.config)["dataset"]["seed"])
        seeds = [base_seed + 997 * index for index in range(args.multi_seed)]
        payload["multi_seed"] = multi_seed_metrics(args.config.resolve(), seeds)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
