"""Fast contract tests for the checked-in VAIC simulation data."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import generate_data as generator  # noqa: E402
import audit_synthetic_quality as quality_audit  # noqa: E402


BASE_CONFIG = ROOT / "config" / "base.yaml"
SCENARIO_CONFIG_DIR = ROOT / "config" / "scenarios"
ANNUAL_DIR = ROOT / "data" / "generated" / "annual"
SCENARIO_DATA_DIR = ROOT / "data" / "generated" / "scenarios"

EXPECTED_SCHEMAS = {
    "nodes": [
        "node_id",
        "name_vi",
        "node_type",
        "location_label",
        "lat",
        "lon",
        "on_river",
        "active",
        "source_type",
    ],
    "legs": [
        "leg_id",
        "from_node_id",
        "to_node_id",
        "mode",
        "distance_km",
        "duration_hr_base",
        "weather_sensitivity",
        "bidirectional",
        "active",
        "source_type",
        "source_note",
    ],
    "commodities": [
        "commodity_id",
        "name_vi",
        "category",
        "perishability_level",
        "max_hold_hours",
        "loss_pct_per_hour",
        "value_vnd_per_kg",
        "needs_reefer",
        "water_ok",
        "compatible_vehicle_types",
        "source_type",
    ],
    "orders": [
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
    ],
    "weather": [
        "ts",
        "node_id",
        "rainfall_mm",
        "river_level_m",
        "flood_risk_idx",
        "road_factor",
        "water_factor",
        "alert_level",
    ],
    "fleet": [
        "vehicle_id",
        "vehicle_type",
        "mode",
        "capacity_ton",
        "current_node_id",
        "status",
        "available_from_ts",
        "cost_fixed_vnd",
        "cost_per_km_vnd",
        "speed_kmh",
        "has_reefer",
        "owner_hub_id",
    ],
    "fuel_prices": [
        "ts",
        "fuel_type",
        "price_vnd_per_liter",
        "adjustment_date",
        "source_type",
    ],
    "freight_rates": [
        "ts",
        "mode",
        "leg_id",
        "vehicle_type",
        "fuel_type",
        "fuel_price_vnd_per_liter",
        "fuel_cost_factor",
        "rate_vnd_per_ton_km",
        "fixed_fee_vnd",
        "demand_idx",
        "rate_type",
    ],
    "weather_bulletins": [
        "bulletin_id",
        "issued_at",
        "valid_from",
        "valid_to",
        "node_id",
        "severity",
        "road_status",
        "water_navigation_status",
        "max_rainfall_mm",
        "max_flood_risk_idx",
        "headline",
        "bulletin_text",
        "evidence_ref",
        "source_type",
    ],
    "ops_notes": [
        "note_id",
        "created_at",
        "hub_id",
        "vehicle_id",
        "note_type",
        "constraint_code",
        "is_blocking",
        "valid_until",
        "note_text",
        "evidence_ref",
        "source_type",
    ],
    "policy_docs": [
        "policy_id",
        "title",
        "effective_from",
        "applies_to",
        "policy_text",
        "citation_ref",
        "source_type",
    ],
}

OPTIMIZER_OUTPUT_COLUMNS = {
    "recommended_route",
    "predicted_cost",
    "selected_vehicle",
    "dispatch_decision",
}

COMPATIBILITY_KEYS = {
    "dataset_orders.json": {
        "hub_id",
        "hub_name",
        "timestamp",
        "loai_hang",
        "khoi_luong_kg",
    },
    "dataset_weather.json": {
        "region",
        "timestamp",
        "canh_bao_mua_lu",
        "muc_nuoc_song_cm",
    },
    "dataset_fleet.json": {
        "vehicle_id",
        "loai",
        "suc_chua_kg",
        "vi_tri_hien_tai",
        "trang_thai",
    },
    "dataset_price.json": {
        "timestamp",
        "gia_nhien_lieu_per_km",
        "gia_thue_xe_tai_per_km",
        "gia_thue_sa_lan_per_km",
    },
}


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def _scenario_csv(scenario: str, table: str, **kwargs: object) -> pd.DataFrame:
    return pd.read_csv(SCENARIO_DATA_DIR / scenario / "csv" / f"{table}.csv", **kwargs)


def test_scenario_config_inherits_base_and_deep_merges_overrides() -> None:
    base = generator.load_config(BASE_CONFIG)
    flood = generator.load_config(SCENARIO_CONFIG_DIR / "S2_flood.yaml")

    assert flood["dataset"]["version"] == base["dataset"]["version"]
    assert flood["dataset"]["default_format"] == base["dataset"]["default_format"]
    assert flood["dataset"]["pack"] == "S2_flood"
    assert flood["nodes"] == base["nodes"]
    assert flood["order_generation"] == base["order_generation"]
    assert flood["compatibility_exports"] == base["compatibility_exports"]
    assert flood["scenario"]["weather"]["rainfall_multiplier"] == 2.20
    assert flood["scenario"]["freight"]["mode_rate_multipliers"]["road"] == 1.08
    assert base["scenario"]["weather"]["rainfall_multiplier"] == 1.00
    assert Path(flood["_runtime"]["config_path"]) == (
        SCENARIO_CONFIG_DIR / "S2_flood.yaml"
    ).resolve()


def test_small_scenario_generation_is_deterministic_in_tmp_path(tmp_path: Path) -> None:
    config_path = SCENARIO_CONFIG_DIR / "S1_normal.yaml"
    seed = 8675309

    _, first_metadata, first_dir = generator.generate_and_write(
        config_path,
        seed_override=seed,
        format_override="json",
        output_override=tmp_path / "first",
    )
    _, second_metadata, second_dir = generator.generate_and_write(
        config_path,
        seed_override=seed,
        format_override="json",
        output_override=tmp_path / "second",
    )

    assert first_dir.parent == tmp_path
    assert second_dir.parent == tmp_path
    assert first_metadata["seed"] == second_metadata["seed"] == seed
    assert first_metadata["row_counts"] == second_metadata["row_counts"]
    assert first_metadata["canonical_checksums"] == second_metadata["canonical_checksums"]
    assert first_metadata["file_checksums"] == second_metadata["file_checksums"]
    assert first_metadata["compatibility_files"] == second_metadata["compatibility_files"]
    assert (first_dir / "metadata.json").read_bytes() == (
        second_dir / "metadata.json"
    ).read_bytes()


def test_canonical_tables_have_exact_frozen_schemas_and_no_optimizer_columns() -> None:
    assert generator.TABLE_SCHEMAS == EXPECTED_SCHEMAS

    for table, expected_columns in EXPECTED_SCHEMAS.items():
        path = ANNUAL_DIR / "csv" / f"{table}.csv"
        columns = pd.read_csv(path, nrows=0).columns.tolist()
        assert columns == expected_columns, table
        assert OPTIMIZER_OUTPUT_COLUMNS.isdisjoint(columns), table


def test_every_contract_stub_has_exact_schema_and_at_least_ten_rows() -> None:
    for table, expected_columns in EXPECTED_SCHEMAS.items():
        path = ROOT / "data" / "stubs" / f"{table}.csv"
        frame = pd.read_csv(path)
        assert frame.columns.tolist() == expected_columns, table
        assert len(frame) >= 10, table


def test_compatibility_json_files_expose_exact_expected_keys() -> None:
    compat_dir = ANNUAL_DIR / "compat"
    for filename, expected_keys in COMPATIBILITY_KEYS.items():
        records = json.loads((compat_dir / filename).read_text(encoding="utf-8"))
        assert records, filename
        assert all(set(record) == expected_keys for record in records), filename


def test_checked_in_scenarios_express_flood_and_price_shock_signals() -> None:
    target_nodes = {"HUB_VITHANH", "HUB_SOCTRANG", "CT_HUB"}
    weather_columns = [
        "node_id",
        "rainfall_mm",
        "flood_risk_idx",
        "road_factor",
        "water_factor",
    ]
    normal_weather = _scenario_csv(
        "S1_normal", "weather", usecols=weather_columns
    ).query("node_id in @target_nodes")
    flood_weather = _scenario_csv(
        "S2_flood", "weather", usecols=weather_columns
    ).query("node_id in @target_nodes")
    for signal in ("rainfall_mm", "flood_risk_idx", "road_factor", "water_factor"):
        assert flood_weather[signal].mean() > normal_weather[signal].mean(), signal

    normal_fuel = _scenario_csv(
        "S1_normal", "fuel_prices", usecols=["fuel_type", "price_vnd_per_liter"]
    ).set_index("fuel_type")["price_vnd_per_liter"]
    shock_fuel = _scenario_csv(
        "S3_price_shock", "fuel_prices", usecols=["ts", "fuel_type", "price_vnd_per_liter"]
    ).sort_values(["fuel_type", "ts"])
    diesel_ratio = (
        shock_fuel.loc[shock_fuel["fuel_type"] == "diesel_005s", "price_vnd_per_liter"]
        / normal_fuel["diesel_005s"]
    )
    marine_ratio = (
        shock_fuel.loc[shock_fuel["fuel_type"] == "marine_diesel", "price_vnd_per_liter"]
        / normal_fuel["marine_diesel"]
    )
    assert np.allclose(diesel_ratio.to_numpy(), [1.05, 1.12, 1.18])
    assert np.allclose(marine_ratio.to_numpy(), [1.01, 1.02, 1.04])
    assert np.isclose(
        shock_fuel.loc[shock_fuel["fuel_type"] == "gasoline", "price_vnd_per_liter"].iloc[0],
        normal_fuel["gasoline"],
    )

    normal_demand = _scenario_csv(
        "S1_normal", "freight_rates", usecols=["mode", "demand_idx"]
    ).groupby("mode")["demand_idx"].mean()
    shock_demand = _scenario_csv(
        "S3_price_shock", "freight_rates", usecols=["mode", "demand_idx"]
    ).groupby("mode")["demand_idx"].mean()
    demand_ratio = shock_demand / normal_demand
    assert np.isclose(demand_ratio["road"], 1.10)
    assert np.isclose(demand_ratio["water"], 1.03)
    assert demand_ratio["road"] > demand_ratio["water"]

    shock_road_factor = (
        _scenario_csv(
            "S3_price_shock",
            "freight_rates",
            usecols=["ts", "mode", "fuel_cost_factor"],
        )
        .query("mode == 'road'")
        .groupby("ts")["fuel_cost_factor"]
        .mean()
    )
    assert shock_road_factor.iloc[-1] > shock_road_factor.iloc[0]

    flood_bulletins = _scenario_csv(
        "S2_flood",
        "weather_bulletins",
        usecols=["node_id", "water_navigation_status"],
    )
    assert (
        flood_bulletins.query("node_id in @target_nodes")["water_navigation_status"]
        == "closed"
    ).any()

    normal_fleet = _scenario_csv(
        "S1_normal", "fleet", usecols=["mode", "status"]
    )
    shock_fleet = _scenario_csv(
        "S3_price_shock", "fleet", usecols=["mode", "status"]
    )
    normal_road_availability = (
        normal_fleet.loc[normal_fleet["mode"] == "road", "status"] == "available"
    ).mean()
    shock_road_availability = (
        shock_fleet.loc[shock_fleet["mode"] == "road", "status"] == "available"
    ).mean()
    assert shock_road_availability < normal_road_availability


def test_checked_in_annual_pack_row_counts_and_required_coverage() -> None:
    config = generator.load_config(BASE_CONFIG)
    metadata = json.loads((ANNUAL_DIR / "metadata.json").read_text(encoding="utf-8"))
    row_counts = metadata["row_counts"]

    active_node_ids = {
        node["node_id"]
        for node in config["nodes"]
        if not node.get("optional", False) or config["dataset"].get("extra_hubs", False)
    }
    active_legs = [
        leg
        for leg in config["legs"]
        if leg["from_node_id"] in active_node_ids and leg["to_node_id"] in active_node_ids
    ]
    start = pd.Timestamp(config["dataset"]["start"])
    end = pd.Timestamp(config["dataset"]["end"])
    weather_timestamps = pd.date_range(
        start, end, freq=f"{config['weather_generation']['frequency_hours']}h"
    )
    fuel_timestamps = pd.date_range(
        start, end, freq=f"{config['fuel_generation']['adjustment_interval_days']}D"
    )
    freight_timestamps = pd.date_range(
        start, end, freq=f"{config['freight_generation']['frequency_hours']}h"
    )
    vehicle_type_count_by_mode = {
        mode: sum(
            profile["mode"] == mode
            for profile in config["fleet_generation"]["vehicle_types"].values()
        )
        for mode in ("road", "water")
    }
    freight_rows_per_timestamp = sum(
        vehicle_type_count_by_mode[leg["mode"]]
        * len(config["freight_generation"]["rate_types"])
        for leg in active_legs
    )
    expected_fleet_rows = sum(
        int(count)
        for allocation in config["fleet_generation"]["allocations"].values()
        for count in allocation.values()
    )

    assert row_counts["nodes"] == len(active_node_ids)
    assert row_counts["legs"] == len(active_legs)
    assert row_counts["commodities"] == len(config["commodities"])
    assert row_counts["weather"] == len(weather_timestamps) * len(active_node_ids)
    assert row_counts["fuel_prices"] == len(fuel_timestamps) * len(
        config["fuel_generation"]["base_prices_vnd_per_liter"]
    )
    assert row_counts["freight_rates"] == (
        len(freight_timestamps) * freight_rows_per_timestamp
    )
    day_count = len(pd.date_range(start.floor("D"), end.floor("D"), freq="D"))
    assert row_counts["weather_bulletins"] == day_count * len(active_node_ids)
    assert row_counts["ops_notes"] == expected_fleet_rows + day_count * len(
        config["order_generation"]["hubs"]
    )
    assert row_counts["policy_docs"] == len(
        config["grounding_generation"]["policy_docs"]
    )
    assert row_counts["fleet"] == expected_fleet_rows
    assert row_counts["orders"] > 0

    for table in EXPECTED_SCHEMAS:
        assert _csv_row_count(ANNUAL_DIR / "csv" / f"{table}.csv") == row_counts[table]

    weather = pd.read_csv(ANNUAL_DIR / "csv" / "weather.csv", usecols=["ts", "node_id"])
    assert set(weather["node_id"]) == active_node_ids
    assert weather["ts"].nunique() == len(weather_timestamps)
    assert weather.groupby("node_id")["ts"].nunique().eq(len(weather_timestamps)).all()
    assert weather["ts"].min() == config["dataset"]["start"]
    assert weather["ts"].max() == config["dataset"]["end"]

    orders = pd.read_csv(
        ANNUAL_DIR / "csv" / "orders.csv",
        usecols=["hub_id", "commodity_id", "arrival_ts"],
    )
    order_months = set(pd.to_datetime(orders["arrival_ts"]).dt.month)
    assert order_months == set(range(1, 13))
    assert set(config["validation"]["required_hubs"]).issubset(orders["hub_id"])
    assert set(config["validation"]["required_commodities"]).issubset(
        orders["commodity_id"]
    )

    fleet = pd.read_csv(
        ANNUAL_DIR / "csv" / "fleet.csv",
        usecols=["vehicle_type", "mode", "status", "current_node_id"],
    )
    assert set(fleet["mode"]) == {"road", "water"}
    assert {"available", "en_route", "maintenance", "reserved"}.issubset(
        fleet["status"]
    )
    assert set(config["fleet_generation"]["vehicle_types"]).issubset(
        fleet["vehicle_type"]
    )
    assert (
        fleet.loc[
            fleet["vehicle_type"].isin(["barge_200t", "barge_500t"]),
            "current_node_id",
        ]
        == "CT_HUB"
    ).all()

    legs = pd.read_csv(
        ANNUAL_DIR / "csv" / "legs.csv",
        usecols=["from_node_id", "to_node_id", "mode"],
    )
    required_hubs = set(config["validation"]["required_hubs"])
    direct_road_hubs = set(
        legs.loc[
            (legs["to_node_id"] == "HCM_MARKET") & (legs["mode"] == "road"),
            "from_node_id",
        ]
    )
    road_to_ct_hubs = set(
        legs.loc[
            (legs["to_node_id"] == "CT_HUB") & (legs["mode"] == "road"),
            "from_node_id",
        ]
    )
    water_to_ct_hubs = set(
        legs.loc[
            (legs["to_node_id"] == "CT_HUB") & (legs["mode"] == "water"),
            "from_node_id",
        ]
    )
    outbound_modes = set(
        legs.loc[
            (legs["from_node_id"] == "CT_HUB")
            & (legs["to_node_id"] == "HCM_MARKET"),
            "mode",
        ]
    )
    assert required_hubs.issubset(direct_road_hubs)
    assert required_hubs.issubset(road_to_ct_hubs)
    assert required_hubs.issubset(water_to_ct_hubs)
    assert outbound_modes == {"road", "water"}


def test_daily_demand_signal_generalizes_across_multiple_seeds() -> None:
    base = generator.load_config(BASE_CONFIG)
    guardrails = base["validation"]["demand_signal_guardrails"]
    seeds = [int(base["dataset"]["seed"]) + offset for offset in (0, 997, 1994)]
    runs = []
    for seed in seeds:
        config = generator.load_config(BASE_CONFIG)
        config["dataset"]["seed"] = seed
        metrics = quality_audit.order_signal_metrics(
            generator.generate_orders(config), config
        )
        runs.append(metrics)
        assert config["order_generation"]["forecast_grain"] == "day"
        assert config["order_generation"]["target_annual_rows"]["min"] <= metrics["rows"]
        assert metrics["rows"] <= config["order_generation"]["target_annual_rows"]["max"]

    for metric, rule_name in (
        ("calendar_oracle_r2_hub_month_dow", "calendar_oracle_r2"),
        ("monthly_tonnage_peak_trough", "monthly_tonnage_peak_trough"),
        ("daily_variance_mean_ratio", "daily_variance_mean_ratio"),
    ):
        values = np.asarray([float(run[metric]) for run in runs])
        rule = guardrails[rule_name]
        assert values.min() >= float(rule["min"]), (metric, values)
        assert values.max() <= float(rule["max"]), (metric, values)

    zero_shares = np.asarray([float(run["hourly_zero_share"]) for run in runs])
    assert zero_shares.max() <= float(guardrails["hourly_zero_share_max"])
    r2_values = np.asarray(
        [float(run["calendar_oracle_r2_hub_month_dow"]) for run in runs]
    )
    assert r2_values.max() - r2_values.min() <= 0.20


def test_held_out_evaluation_set_is_separate_and_reproducible() -> None:
    eval_dir = ROOT / "eval"
    reference = pd.read_csv(eval_dir / "reference_routes.csv")
    metadata = json.loads((eval_dir / "metadata.json").read_text(encoding="utf-8"))
    config = generator.load_config(BASE_CONFIG)

    assert len(reference) == config["evaluation"]["target_rows"] == 50
    assert reference["eval_id"].is_unique
    assert not reference.duplicated(["pack", "order_id"]).any()
    assert set(reference["reference_route"]).issubset(
        {"A_DIRECT_ROAD", "B_ROAD_VIA_CT", "C_WATER_VIA_CT", "INFEASIBLE"}
    )
    assert metadata["checksums"]["reference_routes.csv"] == generator.sha256_file(
        eval_dir / "reference_routes.csv"
    )
    assert metadata["dataset_version"] == config["dataset"]["version"]
    for table in EXPECTED_SCHEMAS:
        columns = pd.read_csv(ANNUAL_DIR / "csv" / f"{table}.csv", nrows=0).columns
        assert OPTIMIZER_OUTPUT_COLUMNS.isdisjoint(columns)
