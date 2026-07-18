#!/usr/bin/env python3
"""Contract and reproducibility validator for the VAIC three-year pack."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

import audit_three_year_quality
import generate_data as generator


def validate(
    config_path: Path, pack_dir: Path, *, reproducibility: bool = True
) -> dict[str, Any]:
    config = generator.load_config(config_path)
    metadata = json.loads((pack_dir / "metadata.json").read_text(encoding="utf-8"))
    csv_dir = pack_dir / "csv"
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    frames: dict[str, pd.DataFrame] = {}
    primary_keys = {
        "nodes": ["node_id"],
        "legs": ["leg_id"],
        "commodities": ["commodity_id"],
        "orders": ["order_id"],
        "fleet": ["vehicle_id"],
        "weather": ["ts", "node_id"],
        "fuel_prices": ["ts", "fuel_type"],
        "freight_rates": ["ts", "leg_id", "vehicle_type", "rate_type"],
        "weather_bulletins": ["bulletin_id"],
        "ops_notes": ["note_id"],
        "policy_docs": ["policy_id"],
    }
    for table, schema in generator.TABLE_SCHEMAS.items():
        path = csv_dir / f"{table}.csv"
        check(f"{table}.exists", path.exists(), str(path))
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        frames[table] = frame
        check(f"{table}.schema", list(frame.columns) == schema, f"columns={list(frame.columns)}")
        check(f"{table}.primary_key", not frame.duplicated(primary_keys[table]).any(), f"keys={primary_keys[table]}")
        check(f"{table}.row_count", len(frame) == int(metadata["row_counts"][table]), f"rows={len(frame)}")

    for table in config["analytics"]["partition_tables"]:
        partition_root = csv_dir / table
        partition_rows = 0
        years: list[int] = []
        for path in sorted(partition_root.glob("year=*/" + table + ".csv")):
            years.append(int(path.parent.name.split("=")[1]))
            partition_rows += len(pd.read_csv(path))
        check(f"{table}.partitions_years", years == [2024, 2025, 2026], f"years={years}")
        check(f"{table}.partitions_conserve_rows", partition_rows == len(frames[table]), f"partition_rows={partition_rows}")

    admin_units = pd.read_csv("data/reference/admin_units.csv")
    node_admin = pd.read_csv("data/reference/node_admin_history.csv")
    check("geography.single_version", set(admin_units["admin_version"]) == {"harmonized_post_2025"}, str(sorted(admin_units["admin_version"].unique())))
    check("geography.one_mapping_per_node", node_admin["node_id"].is_unique, f"rows={len(node_admin)}")
    check("geography.active_nodes_covered", set(frames["nodes"]["node_id"]).issubset(set(node_admin["node_id"])), "all active nodes map to post-2025 geography")

    audit = audit_three_year_quality.audit(config_path, pack_dir)
    for name, condition in audit["checks"].items():
        check(f"quality.{name}", bool(condition), str(audit["metrics"].get(name, "see quality report")))

    forecast_path = pack_dir / "analytics" / "forecast_evaluation.csv"
    forecast_meta_path = pack_dir / "analytics" / "forecast_evaluation_metadata.json"
    check("forecast.files_exist", forecast_path.exists() and forecast_meta_path.exists(), "forecast evaluation artifacts")
    if forecast_path.exists() and forecast_meta_path.exists():
        forecast = pd.read_csv(forecast_path)
        forecast_meta = json.loads(forecast_meta_path.read_text(encoding="utf-8"))
        aggregate = forecast[
            (forecast["scope"] == "all_hubs")
            & (forecast["grain"] == "daily_hub")
        ].set_index("model")
        check("forecast.strict_time_split", forecast_meta["random_split_used"] is False and forecast_meta["test_period"]["start"] == "2026-01-01", str(forecast_meta["test_period"]))
        check("forecast.model_beats_rolling_wape", float(aggregate.loc["calendar_trend_ridge", "wape"]) < float(aggregate.loc["rolling_28d", "wape"]), f"model={aggregate.loc['calendar_trend_ridge', 'wape']:.6f}, rolling={aggregate.loc['rolling_28d', 'wape']:.6f}")

    if reproducibility:
        with tempfile.TemporaryDirectory(prefix="vaic_three_year_repro_") as temp_dir:
            regenerated_tables = generator.generate_tables(generator.load_config(config_path))
            regenerated = {
                table: generator.canonical_checksum(frame)
                for table, frame in regenerated_tables.items()
            }
            check("reproducibility.canonical_checksums", regenerated == metadata["canonical_checksums"], "same seed/config regenerates identical canonical tables")

    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "dataset_version": metadata["dataset_version"],
        "checks_passed": len(checks) - len(failures),
        "checks_failed": len(failures),
        "warnings": ["All growth, seasonality and cross-domain coefficients remain synthetic assumptions."],
        "errors": failures,
        "checks": checks,
        "reproducibility_checked": reproducibility,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base_3y.yaml")
    parser.add_argument("--pack-dir", default="data/generated/three_year")
    parser.add_argument("--output", default="reports/validation_three_year_v4.json")
    parser.add_argument("--skip-reproducibility", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.config), Path(args.pack_dir), reproducibility=not args.skip_reproducibility)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Validation {result['status']}: {result['checks_passed']} passed, {result['checks_failed']} failed. Report: {output.resolve()}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
