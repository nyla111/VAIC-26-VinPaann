#!/usr/bin/env python3
"""Build a held-out golden route set by exhaustive candidate enumeration.

Labels are written only under ``eval/``.  Canonical input packs remain free of
optimizer outputs, which prevents label leakage into downstream agents.
"""

from __future__ import annotations

import argparse
import hashlib
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


ROUTE_IDS = ("A_DIRECT_ROAD", "B_ROAD_VIA_CT", "C_WATER_VIA_CT")
OUTPUT_COLUMNS = [
    "eval_id",
    "pack",
    "order_id",
    "decision_ts",
    "reference_route",
    "reference_total_cost_vnd",
    "reference_elapsed_hr",
    "feasible_routes",
    "infeasible_routes",
    "rationale_codes",
    "route_a_cost_vnd",
    "route_b_cost_vnd",
    "route_c_cost_vnd",
    "source_order_sha256",
]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _order_checksum(order: pd.Series) -> str:
    payload = json.dumps(order.to_dict(), ensure_ascii=False, sort_keys=True, default=str)
    return _sha256_text(payload)


def _route_leg_ids(hub_id: str) -> dict[str, list[str]]:
    prefixes = {
        "HUB_VITHANH": "VT",
        "HUB_LONGXUYEN": "LX",
        "HUB_SOCTRANG": "ST",
        "HUB_VINHLONG": "VL",
    }
    prefix = prefixes[hub_id]
    return {
        "A_DIRECT_ROAD": [f"LEG_{prefix}_HCM_ROAD"],
        "B_ROAD_VIA_CT": [f"LEG_{prefix}_CT_ROAD", "LEG_CT_HCM_ROAD"],
        "C_WATER_VIA_CT": [f"LEG_{prefix}_CT_WATER", "LEG_CT_HCM_WATER"],
    }


def _latest_rows(frame: pd.DataFrame, timestamp: pd.Timestamp, ts_column: str = "ts") -> pd.DataFrame:
    times = pd.to_datetime(frame[ts_column])
    return frame.loc[times <= timestamp]


def _weather_factor(
    weather: pd.DataFrame,
    leg: pd.Series,
    mode: str,
    decision_ts: pd.Timestamp,
) -> float:
    factor_column = "road_factor" if mode == "road" else "water_factor"
    values = []
    for node_id in (leg["from_node_id"], leg["to_node_id"]):
        subset = weather.loc[weather["node_id"] == node_id]
        subset = _latest_rows(subset, decision_ts)
        if subset.empty:
            return math.inf
        latest_time = pd.to_datetime(subset["ts"]).max()
        values.append(float(subset.loc[pd.to_datetime(subset["ts"]) == latest_time, factor_column].iloc[0]))
    return max(values)


def _is_route_closed(
    bulletins: pd.DataFrame,
    node_ids: set[str],
    mode: str,
    decision_ts: pd.Timestamp,
) -> bool:
    valid_from = pd.to_datetime(bulletins["valid_from"])
    valid_to = pd.to_datetime(bulletins["valid_to"])
    active = bulletins.loc[
        bulletins["node_id"].isin(node_ids)
        & (valid_from <= decision_ts)
        & (valid_to >= decision_ts)
    ]
    if active.empty:
        return False
    column = "road_status" if mode == "road" else "water_navigation_status"
    return bool((active[column] == "closed").any())


def _best_leg_cost(
    freight: pd.DataFrame,
    fleet_profiles: dict[str, dict[str, Any]],
    compatible_types: list[str],
    leg_id: str,
    mode: str,
    weight_ton: float,
    distance_km: float,
    decision_ts: pd.Timestamp,
    rate_type: str,
) -> tuple[float, str | None]:
    best = math.inf
    best_type: str | None = None
    for vehicle_type in compatible_types:
        profile = fleet_profiles.get(vehicle_type)
        if not profile or profile["mode"] != mode:
            continue
        quotes = freight.loc[
            (freight["leg_id"] == leg_id)
            & (freight["vehicle_type"] == vehicle_type)
            & (freight["rate_type"] == rate_type)
        ]
        quotes = _latest_rows(quotes, decision_ts)
        if quotes.empty:
            continue
        latest_time = pd.to_datetime(quotes["ts"]).max()
        quote = quotes.loc[pd.to_datetime(quotes["ts"]) == latest_time].iloc[0]
        capacity = float(profile["capacity_ton"])
        trips = max(1, int(math.ceil(weight_ton / capacity)))
        cost = (
            float(quote["fixed_fee_vnd"]) * trips
            + float(quote["rate_vnd_per_ton_km"]) * weight_ton * distance_km
        )
        if cost < best:
            best = cost
            best_type = vehicle_type
    return best, best_type


def evaluate_order(
    order: pd.Series,
    pack: str,
    config: dict[str, Any],
    tables: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    decision_ts = pd.Timestamp(order["ready_ts"])
    deadline_ts = pd.Timestamp(order["deadline_ts"])
    commodity = tables["commodities"].set_index("commodity_id").loc[order["commodity_id"]]
    compatible_types = str(commodity["compatible_vehicle_types"]).split("|")
    profiles = config["fleet_generation"]["vehicle_types"]
    legs = tables["legs"].set_index("leg_id")
    route_legs = _route_leg_ids(str(order["hub_id"]))
    evaluations: dict[str, dict[str, Any]] = {}
    weight_ton = float(order["weight_kg"]) / 1000.0
    rate_type = str(config["evaluation"]["rate_type"])

    for route_id in ROUTE_IDS:
        leg_ids = route_legs[route_id]
        mode = "water" if route_id == "C_WATER_VIA_CT" else "road"
        reasons: list[str] = []
        if mode == "water" and not bool(commodity["water_ok"]):
            reasons.append("COMMODITY_NOT_WATER_COMPATIBLE")
        node_ids = set()
        for leg_id in leg_ids:
            if leg_id not in legs.index:
                reasons.append("MISSING_LEG")
                continue
            node_ids.update([legs.loc[leg_id, "from_node_id"], legs.loc[leg_id, "to_node_id"]])
        if _is_route_closed(tables["weather_bulletins"], node_ids, mode, decision_ts):
            reasons.append("ROUTE_CLOSED")

        freight_cost = 0.0
        elapsed = float(config["evaluation"]["transfer_wait_hours"][route_id])
        vehicle_types: list[str] = []
        if not reasons:
            for leg_id in leg_ids:
                leg = legs.loc[leg_id]
                leg_cost, vehicle_type = _best_leg_cost(
                    tables["freight_rates"],
                    profiles,
                    compatible_types,
                    leg_id,
                    mode,
                    weight_ton,
                    float(leg["distance_km"]),
                    decision_ts,
                    rate_type,
                )
                if not math.isfinite(leg_cost) or vehicle_type is None:
                    reasons.append("NO_COMPATIBLE_QUOTE")
                    break
                freight_cost += leg_cost
                vehicle_types.append(vehicle_type)
                elapsed += float(leg["duration_hr_base"]) * _weather_factor(
                    tables["weather"], leg, mode, decision_ts
                )
        if not reasons and decision_ts + pd.Timedelta(hours=elapsed) > deadline_ts:
            reasons.append("DEADLINE_INFEASIBLE")

        if reasons:
            evaluations[route_id] = {
                "feasible": False,
                "cost": math.inf,
                "elapsed": elapsed,
                "reasons": reasons,
                "vehicle_types": vehicle_types,
            }
        else:
            loss_cost = (
                float(order["weight_kg"])
                * float(commodity["value_vnd_per_kg"])
                * float(commodity["loss_pct_per_hour"])
                / 100.0
                * elapsed
            )
            evaluations[route_id] = {
                "feasible": True,
                "cost": freight_cost + loss_cost,
                "elapsed": elapsed,
                "reasons": [],
                "vehicle_types": vehicle_types,
            }

    feasible = [route for route, result in evaluations.items() if result["feasible"]]
    reference_route = min(feasible, key=lambda route: evaluations[route]["cost"]) if feasible else "INFEASIBLE"
    reference = evaluations.get(reference_route, {"cost": math.nan, "elapsed": math.nan})
    if reference_route == "C_WATER_VIA_CT":
        rationale = "BULK_WATER_ECONOMICS|DEADLINE_FEASIBLE"
    elif reference_route == "B_ROAD_VIA_CT":
        rationale = "CT_CONSOLIDATION_PATH|DEADLINE_FEASIBLE"
    elif reference_route == "A_DIRECT_ROAD":
        rationale = "DIRECT_ROUTE_COST_OR_DEADLINE"
    else:
        rationale = "NO_DEADLINE_FEASIBLE_ROUTE"
    infeasible = [
        f"{route}:{'+'.join(result['reasons'])}"
        for route, result in evaluations.items()
        if not result["feasible"]
    ]

    return {
        "pack": pack,
        "order_id": order["order_id"],
        "decision_ts": order["ready_ts"],
        "reference_route": reference_route,
        "reference_total_cost_vnd": reference["cost"],
        "reference_elapsed_hr": reference["elapsed"],
        "feasible_routes": "|".join(feasible),
        "infeasible_routes": "|".join(infeasible),
        "rationale_codes": rationale,
        "route_a_cost_vnd": evaluations["A_DIRECT_ROAD"]["cost"],
        "route_b_cost_vnd": evaluations["B_ROAD_VIA_CT"]["cost"],
        "route_c_cost_vnd": evaluations["C_WATER_VIA_CT"]["cost"],
        "source_order_sha256": _order_checksum(order),
    }


def _load_pack(data_root: Path, pack: str) -> dict[str, pd.DataFrame]:
    path = data_root / "scenarios" / pack / "csv"
    names = (
        "orders",
        "commodities",
        "legs",
        "weather",
        "freight_rates",
        "weather_bulletins",
    )
    return {name: pd.read_csv(path / f"{name}.csv") for name in names}


def _select_stratified(rows: list[dict[str, Any]], orders: pd.DataFrame, quota: int) -> list[dict[str, Any]]:
    order_dims = orders.set_index("order_id")[["hub_id", "commodity_id"]]
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        dims = order_dims.loc[row["order_id"]]
        key = (str(dims["hub_id"]), str(dims["commodity_id"]))
        buckets.setdefault(key, []).append(row)
    for values in buckets.values():
        values.sort(key=lambda item: _sha256_text(f"{item['pack']}|{item['order_id']}"))
    selected: list[dict[str, Any]] = []
    keys = sorted(buckets)
    while len(selected) < quota and keys:
        remaining = []
        for key in keys:
            if buckets[key] and len(selected) < quota:
                selected.append(buckets[key].pop(0))
            if buckets[key]:
                remaining.append(key)
        keys = remaining
    return selected


def build(config_path: Path, data_root: Path) -> pd.DataFrame:
    config = generator.load_config(config_path)
    selected: list[dict[str, Any]] = []
    for pack, quota in config["evaluation"]["pack_quotas"].items():
        tables = _load_pack(data_root, str(pack))
        candidates = [
            evaluate_order(order, str(pack), config, tables)
            for _, order in tables["orders"].iterrows()
            if order["status"] != "cancelled"
        ]
        selected.extend(_select_stratified(candidates, tables["orders"], int(quota)))

    selected.sort(key=lambda row: (row["pack"], row["order_id"]))
    for index, row in enumerate(selected, start=1):
        row["eval_id"] = f"EVAL_ROUTE_{index:03d}"
        for column in (
            "reference_total_cost_vnd",
            "reference_elapsed_hr",
            "route_a_cost_vnd",
            "route_b_cost_vnd",
            "route_c_cost_vnd",
        ):
            value = row[column]
            row[column] = round(float(value), 6) if math.isfinite(float(value)) else None
    return pd.DataFrame(selected).loc[:, OUTPUT_COLUMNS]


def write_outputs(frame: pd.DataFrame, output_dir: Path, config: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "reference_routes.csv"
    json_path = output_dir / "reference_routes.json"
    frame.to_csv(csv_path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.6f")
    json_path.write_text(
        frame.to_json(orient="records", force_ascii=False, double_precision=6) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    metadata = {
        "dataset_version": config["dataset"]["version"],
        "algorithm_version": config["evaluation"]["algorithm_version"],
        "target_rows": int(config["evaluation"]["target_rows"]),
        "actual_rows": int(len(frame)),
        "candidate_routes": list(ROUTE_IDS),
        "pack_counts": frame["pack"].value_counts().sort_index().to_dict(),
        "reference_route_counts": frame["reference_route"].value_counts().sort_index().to_dict(),
        "checksums": {
            "reference_routes.csv": generator.sha256_file(csv_path),
            "reference_routes.json": generator.sha256_file(json_path),
        },
        "leakage_control": "Labels are stored only in eval/ and are absent from canonical packs.",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "base.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval")
    args = parser.parse_args()
    config = generator.load_config(args.config)
    frame = build(args.config.resolve(), args.data_root.resolve())
    if len(frame) != int(config["evaluation"]["target_rows"]):
        raise ValueError(f"Expected {config['evaluation']['target_rows']} eval rows, got {len(frame)}")
    write_outputs(frame, args.output_dir.resolve(), config)
    print(
        json.dumps(
            {
                "status": "OK",
                "rows": len(frame),
                "route_counts": frame["reference_route"].value_counts().to_dict(),
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
