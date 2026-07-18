"""Fast acceptance tests for the 2024-2026 temporal pack."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import generate_data as generator  # noqa: E402


CONFIG = ROOT / "config" / "base_3y.yaml"
PACK = ROOT / "data" / "generated" / "three_year"


def test_three_year_time_contract_and_ids() -> None:
    config = generator.load_config(CONFIG)
    orders = pd.read_csv(PACK / "csv" / "orders.csv")
    weather = pd.read_csv(PACK / "csv" / "weather.csv")
    order_time = pd.to_datetime(orders["arrival_ts"])
    weather_time = pd.to_datetime(weather["ts"])
    assert config["dataset"]["start"].startswith("2024-01-01")
    assert config["dataset"]["end"].startswith("2026-12-31")
    assert order_time.dt.strftime("%Y-%m").nunique() == 36
    assert weather_time.dt.strftime("%Y-%m").nunique() == 36
    assert orders["arrival_ts"].str.endswith("+07:00").all()
    assert weather["ts"].str.endswith("+07:00").all()
    assert (
        orders["order_id"].str.extract(r"ORD_(\d{4})_")[0].astype(int).to_numpy()
        == order_time.dt.year.to_numpy()
    ).all()


def test_weather_has_every_hour_for_every_node() -> None:
    config = generator.load_config(CONFIG)
    weather = pd.read_csv(PACK / "csv" / "weather.csv")
    nodes = pd.read_csv(PACK / "csv" / "nodes.csv")
    expected_hours = len(
        pd.date_range(config["dataset"]["start"], config["dataset"]["end"], freq="h")
    )
    assert len(weather) == expected_hours * len(nodes)
    assert weather.groupby("node_id")["ts"].nunique().eq(expected_hours).all()


def test_geography_uses_only_post_merger_names() -> None:
    admin = pd.read_csv(ROOT / "data" / "reference" / "admin_units.csv")
    mapping = pd.read_csv(ROOT / "data" / "reference" / "node_admin_history.csv")
    monthly = pd.read_csv(PACK / "analytics" / "monthly_trends.csv")
    compat_weather = pd.read_json(PACK / "compat" / "dataset_weather.json")
    assert set(admin["admin_version"]) == {"harmonized_post_2025"}
    assert mapping["node_id"].is_unique
    assert set(monthly["admin_version"]) == {"harmonized_post_2025"}
    assert set(monthly.loc[monthly["hub_id"].isin(["HUB_VITHANH", "HUB_SOCTRANG"]), "admin_name"]) == {"Cần Thơ"}
    assert set(compat_weather["region"]) == {
        "an_giang",
        "can_tho",
        "thanh_pho_ho_chi_minh",
        "vinh_long",
    }


def test_monthly_signal_and_growth_are_bounded() -> None:
    config = generator.load_config(CONFIG)
    guardrails = config["validation"]["temporal_guardrails"]
    monthly = pd.read_csv(PACK / "analytics" / "monthly_trends.csv")
    total = monthly.groupby("month")["total_weight_tons"].sum()
    peak_trough = float(total.max() / total.min())
    assert float(guardrails["monthly_peak_trough"]["min"]) <= peak_trough
    assert peak_trough <= float(guardrails["monthly_peak_trough"]["max"])
    assert float(total.autocorr(lag=12)) >= float(guardrails["lag12_autocorrelation_min"])
    assert monthly.groupby("commodity_id")["month"].nunique().min() >= 30


def test_partitions_conserve_canonical_rows() -> None:
    config = generator.load_config(CONFIG)
    for table in config["analytics"]["partition_tables"]:
        canonical_rows = len(pd.read_csv(PACK / "csv" / f"{table}.csv"))
        paths = sorted((PACK / "csv" / table).glob(f"year=*/{table}.csv"))
        assert [int(path.parent.name.split("=")[1]) for path in paths] == [2024, 2025, 2026]
        assert sum(len(pd.read_csv(path)) for path in paths) == canonical_rows


def test_forecast_uses_strict_time_split() -> None:
    metadata = json.loads(
        (PACK / "analytics" / "forecast_evaluation_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = pd.read_csv(PACK / "analytics" / "forecast_evaluation.csv")
    daily = metrics[
        (metrics["scope"] == "all_hubs") & (metrics["grain"] == "daily_hub")
    ].set_index("model")
    assert metadata["random_split_used"] is False
    assert metadata["train_period"]["end"] == "2025-12-31"
    assert metadata["test_period"]["start"] == "2026-01-01"
    assert daily.loc["calendar_trend_ridge", "wape"] < daily.loc["rolling_28d", "wape"]


def test_resolved_year_effects_are_persisted() -> None:
    metadata = json.loads((PACK / "metadata.json").read_text(encoding="utf-8"))
    resolved = metadata["resolved_temporal_effects"]
    assert set(resolved["demand_year_noise"]) == {"2024", "2025", "2026"}
    assert set(resolved["year_weather_anomaly"]) == {"2024", "2025", "2026"}
