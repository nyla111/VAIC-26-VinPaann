#!/usr/bin/env python3
"""Deterministic semi-synthetic data generator for the VAIC logistics demo."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml


TABLE_SCHEMAS: dict[str, list[str]] = {
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

TABLE_ORDER = list(TABLE_SCHEMAS)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings; lists and scalar values are replaced."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load YAML with an optional relative ``extends`` chain."""
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    parent = raw.pop("extends", None)
    if parent:
        base = load_config(path.parent / parent)
        config = deep_merge(base, raw)
    else:
        config = raw
    config["_runtime"] = {"config_path": str(path)}
    return config


def iso_timestamp(value: pd.Timestamp) -> str:
    return value.isoformat(timespec="seconds")


def time_index(config: dict[str, Any], frequency_hours: int = 1) -> pd.DatetimeIndex:
    dataset = config["dataset"]
    start = pd.Timestamp(dataset["start"])
    end = pd.Timestamp(dataset["end"])
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("dataset.start and dataset.end must include a timezone offset")
    return pd.date_range(start=start, end=end, freq=f"{frequency_hours}h")


def component_rng(config: dict[str, Any], component: str) -> np.random.Generator:
    seed = int(config["dataset"]["seed"])
    offset = int(config["rng_stream_offsets"][component])
    return np.random.default_rng(seed + offset)


def normalize_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Freeze columns, stable row order, null representation, and precision."""
    expected = TABLE_SCHEMAS[name]
    missing = [column for column in expected if column not in frame.columns]
    if missing:
        raise ValueError(f"{name}: missing generated columns {missing}")
    frame = frame.loc[:, expected].copy()
    for column in frame.select_dtypes(include=["float", "float32", "float64"]).columns:
        frame[column] = frame[column].round(6)
    return frame.reset_index(drop=True)


def build_nodes(config: dict[str, Any], include_optional: bool = False) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    extra_hubs = bool(config["dataset"].get("extra_hubs", False))
    for node in config["nodes"]:
        if node.get("optional", False) and not (include_optional or extra_hubs):
            continue
        rows.append({column: node[column] for column in TABLE_SCHEMAS["nodes"]})
    return normalize_frame("nodes", pd.DataFrame(rows))


def build_legs(config: dict[str, Any], nodes: pd.DataFrame) -> pd.DataFrame:
    allowed_nodes = set(nodes["node_id"])
    rows = [
        {column: leg[column] for column in TABLE_SCHEMAS["legs"]}
        for leg in config["legs"]
        if leg["from_node_id"] in allowed_nodes and leg["to_node_id"] in allowed_nodes
    ]
    return normalize_frame("legs", pd.DataFrame(rows))


def build_commodities(config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for commodity in config["commodities"]:
        row = {column: commodity[column] for column in TABLE_SCHEMAS["commodities"]}
        row["compatible_vehicle_types"] = "|".join(commodity["compatible_vehicle_types"])
        rows.append(row)
    return normalize_frame("commodities", pd.DataFrame(rows))


def _normalized(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0 or array.mean() <= 0:
        raise ValueError("Multiplier arrays must have a positive mean")
    return array / array.mean()


def generate_orders(config: dict[str, Any]) -> pd.DataFrame:
    rng = component_rng(config, "orders")
    settings = config["order_generation"]
    scenario_multiplier = float(config["scenario"]["order_multiplier"])
    hourly = _normalized(settings["hourly_arrival_multipliers"])
    weekday = _normalized(settings["weekday_multipliers"])
    shared_monthly = _normalized(settings["shared_monthly_multipliers"])
    shared_weight = float(settings["shared_seasonality_weight"])
    if not 0.0 <= shared_weight <= 1.0:
        raise ValueError("order_generation.shared_seasonality_weight must be in [0, 1]")
    commodity_config = {row["commodity_id"]: row for row in config["commodities"]}
    status_names = list(settings["status_probabilities"])
    status_probabilities = np.asarray(list(settings["status_probabilities"].values()), dtype=float)
    status_probabilities /= status_probabilities.sum()
    records: list[dict[str, Any]] = []

    hourly_timestamps = time_index(config)
    days = pd.DatetimeIndex(hourly_timestamps.floor("D").unique())
    available_hours = {
        day: hourly_timestamps[hourly_timestamps.floor("D") == day]
        for day in days
    }

    latent_cfg = settings.get("daily_latent", {})
    latent_enabled = bool(latent_cfg.get("enabled", False))
    persistence = float(latent_cfg.get("persistence", 0.0))
    regional_std = float(latent_cfg.get("regional_log_std", 0.0))
    hub_std = float(latent_cfg.get("hub_log_std", 0.0))
    latent_clip = latent_cfg.get("clip", [0.0, float("inf")])
    innovation_scale = math.sqrt(max(0.0, 1.0 - persistence**2))
    regional_state = 0.0
    hub_states = {hub_id: 0.0 for hub_id in settings["hubs"]}
    daily_latent: dict[tuple[pd.Timestamp, str], float] = {}
    for day in days:
        if latent_enabled:
            regional_state = persistence * regional_state + float(
                rng.normal(0.0, regional_std * innovation_scale)
            )
        for hub_id in settings["hubs"]:
            if latent_enabled:
                hub_states[hub_id] = persistence * hub_states[hub_id] + float(
                    rng.normal(0.0, hub_std * innovation_scale)
                )
                multiplier = math.exp(regional_state + hub_states[hub_id])
                multiplier = float(
                    np.clip(multiplier, float(latent_clip[0]), float(latent_clip[1]))
                )
            else:
                multiplier = 1.0
            daily_latent[(day, hub_id)] = multiplier

    for day in days:
        for hub_id, hub_profile in settings["hubs"].items():
            base_mix = hub_profile["commodity_mix"]
            commodity_ids = list(base_mix)
            seasonal_weights = np.asarray(
                [
                    float(base_mix[commodity_id])
                    * float(commodity_config[commodity_id]["monthly_multipliers"][day.month - 1])
                    for commodity_id in commodity_ids
                ],
                dtype=float,
            )
            commodity_seasonal_volume = float(
                seasonal_weights.sum() / sum(base_mix.values())
            )
            seasonal_volume = (
                shared_weight * float(shared_monthly[day.month - 1])
                + (1.0 - shared_weight) * commodity_seasonal_volume
            )
            commodity_probabilities = seasonal_weights / seasonal_weights.sum()
            expected = (
                float(hub_profile["base_daily_orders"])
                * weekday[day.weekday()]
                * seasonal_volume
                * daily_latent[(day, hub_id)]
                * scenario_multiplier
            )
            count = int(rng.poisson(expected))
            if not count:
                continue
            selected = rng.choice(commodity_ids, size=count, p=commodity_probabilities)
            day_hours = available_hours[day]
            hour_probabilities = np.asarray(
                [hourly[timestamp.hour] for timestamp in day_hours], dtype=float
            )
            hour_probabilities /= hour_probabilities.sum()
            selected_hours = rng.choice(
                len(day_hours), size=count, p=hour_probabilities
            )
            for commodity_id, hour_position in zip(selected, selected_hours):
                commodity = commodity_config[str(commodity_id)]
                distribution = commodity["weight_distribution"]
                weight_kg = float(
                    np.clip(
                        rng.lognormal(
                            mean=math.log(float(distribution["median_kg"])),
                            sigma=float(distribution["log_sigma"]),
                        ),
                        float(distribution["min_kg"]),
                        float(distribution["max_kg"]),
                    )
                )
                minute_low, minute_high = settings["minute_range"]
                base_hour = day_hours[int(hour_position)]
                max_minute = int(minute_high)
                if base_hour == hourly_timestamps[-1]:
                    max_minute = min(max_minute, 0)
                minute = int(rng.integers(int(minute_low), max_minute + 1))
                arrival = base_hour + pd.Timedelta(minutes=minute)
                delay = settings["ready_delay_hours"]
                ready_delay = float(
                    np.clip(
                        rng.gamma(float(delay["gamma_shape"]), float(delay["gamma_scale"])),
                        float(delay["min"]),
                        float(delay["max"]),
                    )
                )
                ready = arrival + pd.Timedelta(hours=ready_delay)
                hold_fraction = rng.uniform(
                    float(settings["deadline_hold_fraction"]["min"]),
                    float(settings["deadline_hold_fraction"]["max"]),
                )
                deadline_hours = max(
                    float(settings["deadline_floor_hours"]),
                    float(commodity["max_hold_hours"]) * float(hold_fraction),
                )
                deadline = ready + pd.Timedelta(hours=deadline_hours)
                deadline_score = 5 - int(
                    np.searchsorted(
                        np.asarray(settings["priority_deadline_threshold_hours"], dtype=float),
                        deadline_hours,
                        side="right",
                    )
                )
                priority_score = (
                    float(commodity["perishability_level"])
                    * float(settings["priority_perishability_weight"])
                    + deadline_score * float(settings["priority_deadline_weight"])
                )
                records.append(
                    {
                        "hub_id": hub_id,
                        "commodity_id": str(commodity_id),
                        "weight_kg": weight_kg,
                        "arrival_ts": iso_timestamp(arrival),
                        "ready_ts": iso_timestamp(ready),
                        "deadline_ts": iso_timestamp(deadline),
                        "destination_node_id": settings["destination_node_id"],
                        "priority_level": int(np.clip(round(priority_score), 1, 5)),
                        "status": str(rng.choice(status_names, p=status_probabilities)),
                    }
                )

    records.sort(key=lambda row: (row["arrival_ts"], row["hub_id"], row["commodity_id"]))
    year = pd.Timestamp(config["dataset"]["start"]).year
    for number, record in enumerate(records, start=1):
        record["order_id"] = f"ORD_{year}_{number:06d}"
    frame = pd.DataFrame(records)
    return normalize_frame("orders", frame)


def _event_lookup(
    timestamp: pd.Timestamp,
    node_id: str,
    events: list[dict[str, Any]],
) -> tuple[float, float]:
    rainfall_add = 0.0
    river_add = 0.0
    for event in events:
        if node_id not in event["affected_nodes"]:
            continue
        if pd.Timestamp(event["start"]) <= timestamp <= pd.Timestamp(event["end"]):
            rainfall_add += float(event["rainfall_add_mm"])
            river_add += float(event["river_level_add_m"])
    return rainfall_add, river_add


def _alert_level(risk: float, thresholds: dict[str, float]) -> str:
    if risk >= float(thresholds["severe"]):
        return "severe"
    if risk >= float(thresholds["warning"]):
        return "warning"
    if risk >= float(thresholds["watch"]):
        return "watch"
    return "none"


def generate_weather(config: dict[str, Any], nodes: pd.DataFrame) -> pd.DataFrame:
    rng = component_rng(config, "weather")
    settings = config["weather_generation"]
    scenario = config["scenario"]["weather"]
    timestamps = time_index(config, int(settings["frequency_hours"]))
    hourly = _normalized(settings["hourly_rain_multipliers"])
    regional = np.zeros(len(timestamps), dtype=float)
    previous = 0.0
    wet_months = set(int(month) for month in settings["wet_months"])
    persistence = float(settings["regional_persistence"])
    for index, timestamp in enumerate(timestamps):
        season = "wet" if timestamp.month in wet_months else "dry"
        event_probability = float(settings["rain_probability"][season])
        innovation = 0.0
        if rng.random() < event_probability:
            scale_key = f"scale_{season}_mm"
            innovation = float(
                rng.gamma(
                    float(settings["regional_gamma"]["shape"]),
                    float(settings["regional_gamma"][scale_key]),
                )
                * hourly[timestamp.hour]
            )
        regional[index] = persistence * previous + (1.0 - persistence) * innovation
        previous = regional[index]

    memory = int(settings["river_seasonality"]["rainfall_memory_hours"])
    regional_memory = (
        pd.Series(regional).rolling(window=memory, min_periods=1).mean().to_numpy()
    )
    events: list[dict[str, Any]] = []
    if not scenario["suppress_base_extreme_events"]:
        events.extend(settings["base_extreme_events"])
    events.extend(scenario.get("extreme_events", []))
    target_multipliers = scenario.get("target_node_multipliers", {})
    node_profiles = settings["node_profiles"]
    flood = settings["flood"]
    node_on_river = dict(zip(nodes["node_id"], nodes["on_river"]))
    records: list[dict[str, Any]] = []

    for time_position, timestamp in enumerate(timestamps):
        month_phase = math.cos(
            2.0
            * math.pi
            * (timestamp.month - float(settings["river_seasonality"]["peak_month"]))
            / 12.0
        )
        for node_id in nodes["node_id"]:
            profile = node_profiles[node_id]
            local_noise = rng.normal(0.0, float(settings["local_noise_std_mm"]))
            target_multiplier = float(target_multipliers.get(node_id, 1.0))
            event_rain, event_river = _event_lookup(timestamp, node_id, events)
            rainfall = max(
                0.0,
                (
                    regional[time_position]
                    * float(profile["rainfall_multiplier"])
                    + max(0.0, local_noise) * float(settings["local_rain_weight"])
                )
                * float(scenario["rainfall_multiplier"])
                * target_multiplier
                + event_rain,
            )

            if bool(node_on_river[node_id]):
                river_level = (
                    float(profile["river_level_base_m"])
                    + float(settings["river_seasonality"]["amplitude_m"]) * month_phase
                    + regional_memory[time_position]
                    * float(settings["river_seasonality"]["rainfall_coefficient_m_per_mm"])
                    + float(scenario["river_level_add_m"])
                    + event_river
                    + rng.normal(
                        0.0,
                        float(settings["river_seasonality"]["local_noise_std_m"]),
                    )
                )
                river_level = max(
                    float(settings["minimum_river_level_m"]), float(river_level)
                )
                river_risk = np.clip(
                    (river_level - float(flood["river_risk_start_m"]))
                    / (
                        float(flood["river_risk_severe_m"])
                        - float(flood["river_risk_start_m"])
                    ),
                    0.0,
                    1.0,
                )
            else:
                river_level = None
                river_risk = 0.0

            rainfall_risk = min(1.0, rainfall / float(flood["rainfall_severe_mm"]))
            if river_level is None:
                risk = rainfall_risk
            else:
                risk = (
                    rainfall_risk * float(flood["rainfall_weight"])
                    + river_risk * float(flood["river_weight"])
                )
            risk = float(
                np.clip(
                    risk + float(scenario["flood_risk_add"]),
                    0.0,
                    float(flood["risk_cap"]),
                )
            )
            road_factor = max(
                1.0,
                1.0
                + risk * float(flood["road_risk_penalty"])
                + rainfall_risk * float(flood["road_rain_penalty"])
                + float(scenario["road_factor_add"]),
            )
            if river_level is None:
                water_factor = float(flood["nonriver_water_factor"])
            elif river_level < float(flood["water_optimal_low_m"]):
                water_factor = 1.0 + (
                    (float(flood["water_optimal_low_m"]) - river_level)
                    / float(flood["water_optimal_low_m"])
                    * float(flood["water_low_penalty"])
                )
            elif river_level > float(flood["water_optimal_high_m"]):
                water_factor = 1.0 + (
                    (river_level - float(flood["water_optimal_high_m"]))
                    / float(flood["water_optimal_high_m"])
                    * float(flood["water_high_penalty"])
                )
            else:
                water_factor = 1.0
            water_factor = max(1.0, water_factor + float(scenario["water_factor_add"]))
            records.append(
                {
                    "ts": iso_timestamp(timestamp),
                    "node_id": node_id,
                    "rainfall_mm": rainfall,
                    "river_level_m": river_level,
                    "flood_risk_idx": risk,
                    "road_factor": road_factor,
                    "water_factor": water_factor,
                    "alert_level": _alert_level(risk, flood["alert_thresholds"]),
                }
            )
    return normalize_frame("weather", pd.DataFrame(records))


def generate_fleet(config: dict[str, Any]) -> pd.DataFrame:
    rng = component_rng(config, "fleet")
    settings = config["fleet_generation"]
    scenario = config["scenario"]["fleet"]
    start = pd.Timestamp(config["dataset"]["start"])
    records: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    short_names = {
        "truck_5t": "TRK5",
        "truck_15t": "TRK15",
        "reefer_8t": "REF8",
        "boat_50t": "BOAT50",
        "barge_200t": "BRG200",
        "barge_500t": "BRG500",
    }
    farm_hubs = set(config["order_generation"]["hubs"])
    for vehicle_type, allocation in settings["allocations"].items():
        profile = settings["vehicle_types"][vehicle_type]
        mode = profile["mode"]
        override_mix = scenario.get(f"{mode}_status_mix")
        mix = override_mix if override_mix is not None else settings["status_mix"]
        statuses = list(mix)
        probabilities = np.asarray(list(mix.values()), dtype=float)
        probabilities /= probabilities.sum()
        counters.setdefault(vehicle_type, 0)
        for node_id, count in allocation.items():
            for _ in range(int(count)):
                counters[vehicle_type] += 1
                status = str(rng.choice(statuses, p=probabilities))
                low, high = settings["available_delay_hours"][status]
                delay = float(rng.uniform(float(low), float(high)))
                records.append(
                    {
                        "vehicle_id": f"VEH_{short_names[vehicle_type]}_{counters[vehicle_type]:03d}",
                        "vehicle_type": vehicle_type,
                        "mode": mode,
                        "capacity_ton": float(profile["capacity_ton"]),
                        "current_node_id": node_id,
                        "status": status,
                        "available_from_ts": iso_timestamp(start + pd.Timedelta(hours=delay)),
                        "cost_fixed_vnd": float(profile["cost_fixed_vnd"]),
                        "cost_per_km_vnd": float(profile["cost_per_km_vnd"]),
                        "speed_kmh": float(profile["speed_kmh"]),
                        "has_reefer": bool(profile["has_reefer"]),
                        "owner_hub_id": node_id if node_id in farm_hubs else None,
                    }
                )
    return normalize_frame("fleet", pd.DataFrame(records))


def generate_fuel_prices(config: dict[str, Any]) -> pd.DataFrame:
    rng = component_rng(config, "fuel")
    settings = config["fuel_generation"]
    interval = int(settings["adjustment_interval_days"])
    base_timestamps = pd.date_range(
        start=pd.Timestamp(config["dataset"]["start"]),
        end=pd.Timestamp(config["dataset"]["end"]),
        freq=f"{interval}D",
    )
    scenario_multipliers = config["scenario"]["fuel_price_multipliers"]
    scenario_paths = config["scenario"].get("fuel_price_paths", {})
    window_start = pd.Timestamp(config["dataset"]["start"])
    window_end = pd.Timestamp(config["dataset"]["end"])
    records: list[dict[str, Any]] = []
    for fuel_type, base_price in settings["base_prices_vnd_per_liter"].items():
        relative_level = 1.0
        base_levels: list[float] = []
        for position, _ in enumerate(base_timestamps):
            if position:
                innovation = float(
                    np.clip(
                        rng.normal(0.0, float(settings["adjustment_volatility_std"])),
                        -float(settings["max_adjustment_fraction"]),
                        float(settings["max_adjustment_fraction"]),
                    )
                )
                relative_level += innovation - float(settings["mean_reversion"]) * (
                    relative_level - 1.0
                )
            base_levels.append(relative_level)

        path = sorted(
            scenario_paths.get(fuel_type, []),
            key=lambda item: int(item["offset_hours"]),
        )
        path_points = [
            (
                window_start + pd.Timedelta(hours=int(item["offset_hours"])),
                float(item["multiplier"]),
            )
            for item in path
            if window_start + pd.Timedelta(hours=int(item["offset_hours"])) <= window_end
        ]
        output_timestamps = sorted(
            set(base_timestamps.tolist()) | {timestamp for timestamp, _ in path_points}
        )
        for timestamp in output_timestamps:
            base_position = int(base_timestamps.searchsorted(timestamp, side="right") - 1)
            base_position = max(0, base_position)
            shock_multiplier = float(scenario_multipliers[fuel_type])
            for path_timestamp, path_multiplier in path_points:
                if path_timestamp <= timestamp:
                    shock_multiplier = path_multiplier
                else:
                    break
            price = (
                float(base_price)
                * float(base_levels[base_position])
                * shock_multiplier
            )
            records.append(
                {
                    "ts": iso_timestamp(timestamp),
                    "fuel_type": fuel_type,
                    "price_vnd_per_liter": price,
                    "adjustment_date": timestamp.date().isoformat(),
                    "source_type": settings["source_type"],
                }
            )
    records.sort(key=lambda row: (row["ts"], row["fuel_type"]))
    return normalize_frame("fuel_prices", pd.DataFrame(records))


def _asof_fuel_price(
    fuel_series: dict[str, tuple[pd.DatetimeIndex, np.ndarray]],
    fuel_type: str,
    timestamp: pd.Timestamp,
) -> float:
    times, prices = fuel_series[fuel_type]
    position = int(times.searchsorted(timestamp.tz_convert("UTC"), side="right") - 1)
    if position < 0:
        raise ValueError(f"No {fuel_type} price available at {timestamp}")
    return float(prices[position])


def generate_freight_rates(
    config: dict[str, Any],
    legs: pd.DataFrame,
    fuel_prices: pd.DataFrame,
) -> pd.DataFrame:
    rng = component_rng(config, "freight")
    settings = config["freight_generation"]
    scenario = config["scenario"]["freight"]
    timestamps = time_index(config, int(settings["frequency_hours"]))
    vehicle_profiles = config["fleet_generation"]["vehicle_types"]
    vehicle_types_by_mode = {
        mode: [
            vehicle_type
            for vehicle_type, profile in vehicle_profiles.items()
            if profile["mode"] == mode
        ]
        for mode in ("road", "water")
    }
    fuel_settings = settings["fuel_pass_through"]
    fuel_series: dict[str, tuple[pd.DatetimeIndex, np.ndarray]] = {}
    for fuel_type, subset in fuel_prices.groupby("fuel_type", sort=False):
        sorted_subset = subset.assign(_time=pd.to_datetime(subset["ts"], utc=True)).sort_values(
            "_time"
        )
        fuel_series[str(fuel_type)] = (
            pd.DatetimeIndex(sorted_subset["_time"]),
            sorted_subset["price_vnd_per_liter"].astype(float).to_numpy(),
        )
    records: list[dict[str, Any]] = []
    for timestamp in timestamps:
        base_demand = (
            float(settings["hourly_demand_multipliers"][timestamp.hour])
            * float(settings["weekday_multipliers"][timestamp.weekday()])
            * float(settings["monthly_multipliers"][timestamp.month - 1])
        )
        for leg in legs.itertuples(index=False):
            mode = leg.mode
            fuel_type = str(fuel_settings["mode_fuel_type"][mode])
            fuel_price = _asof_fuel_price(fuel_series, fuel_type, timestamp)
            base_fuel_price = float(
                config["fuel_generation"]["base_prices_vnd_per_liter"][fuel_type]
            )
            beta = float(fuel_settings["beta_by_mode"][mode])
            fuel_cost_factor = max(
                float(fuel_settings["minimum_factor"]),
                1.0 + beta * (fuel_price / base_fuel_price - 1.0),
            )
            demand_idx = base_demand * float(
                scenario["mode_demand_multipliers"][mode]
            )
            leg_multiplier = float(settings["leg_rate_multipliers"][leg.leg_id])
            for vehicle_type in vehicle_types_by_mode[mode]:
                base = settings["vehicle_rates"][vehicle_type]
                for rate_type in settings["rate_types"]:
                    discount = (
                        float(settings["contract_discount"])
                        if rate_type == "contract"
                        else 1.0
                    )
                    noise = max(
                        float(settings["minimum_rate_noise_multiplier"]),
                        1.0
                        + rng.normal(
                            0.0,
                            float(settings["rate_volatility_std"][rate_type]),
                        ),
                    )
                    mode_multiplier = float(
                        scenario["mode_rate_multipliers"][mode]
                    )
                    records.append(
                        {
                            "ts": iso_timestamp(timestamp),
                            "mode": mode,
                            "leg_id": leg.leg_id,
                            "vehicle_type": vehicle_type,
                            "fuel_type": fuel_type,
                            "fuel_price_vnd_per_liter": fuel_price,
                            "fuel_cost_factor": fuel_cost_factor,
                            "rate_vnd_per_ton_km": float(
                                base["rate_vnd_per_ton_km"]
                            )
                            * leg_multiplier
                            * demand_idx
                            * discount
                            * noise
                            * mode_multiplier
                            * fuel_cost_factor,
                            "fixed_fee_vnd": float(base["fixed_fee_vnd"])
                            * leg_multiplier
                            * discount
                            * mode_multiplier,
                            "demand_idx": demand_idx,
                            "rate_type": rate_type,
                        }
                    )
    return normalize_frame("freight_rates", pd.DataFrame(records))


def generate_weather_bulletins(
    config: dict[str, Any],
    nodes: pd.DataFrame,
    weather: pd.DataFrame,
) -> pd.DataFrame:
    settings = config["grounding_generation"]["weather_bulletins"]
    frame = weather.copy()
    frame["_time"] = pd.to_datetime(frame["ts"])
    frame["_date"] = frame["_time"].dt.date
    node_names = nodes.set_index("node_id")["name_vi"].to_dict()
    on_river = nodes.set_index("node_id")["on_river"].astype(bool).to_dict()
    severity_rank = {"none": 0, "watch": 1, "warning": 2, "severe": 3}
    rank_severity = {value: key for key, value in severity_rank.items()}
    records: list[dict[str, Any]] = []

    for (date_value, node_id), subset in frame.groupby(["_date", "node_id"], sort=True):
        subset = subset.sort_values("_time")
        max_rain = float(subset["rainfall_mm"].max())
        max_risk = float(subset["flood_risk_idx"].max())
        severity = rank_severity[
            max(severity_rank[str(value)] for value in subset["alert_level"])
        ]
        max_road = float(subset["road_factor"].max())
        if max_road >= float(settings["road_closed_factor"]):
            road_status = "closed"
        elif max_road >= float(settings["road_restricted_factor"]):
            road_status = "restricted"
        else:
            road_status = "open"

        river_values = subset["river_level_m"].dropna().astype(float)
        if not bool(on_river[str(node_id)]) or river_values.empty:
            water_status = "not_applicable"
        elif (
            float(river_values.max()) >= float(settings["water_closed_high_m"])
            or float(river_values.min()) <= float(settings["water_closed_low_m"])
        ):
            water_status = "closed"
        elif (
            float(subset["water_factor"].max())
            >= float(settings["water_caution_factor"])
        ):
            water_status = "caution"
        else:
            water_status = "open"

        status_vi = {
            "open": "thông thường",
            "restricted": "hạn chế",
            "closed": "tạm ngưng",
            "caution": "cần thận trọng",
            "not_applicable": "không áp dụng",
        }
        headline = (
            f"{node_names[str(node_id)]}: cảnh báo {severity}, "
            f"đường bộ {status_vi[road_status]}"
        )
        bulletin_text = (
            f"Bản tin mô phỏng cho {node_names[str(node_id)]} ngày {date_value.isoformat()}. "
            f"Mưa cực đại theo giờ {max_rain:.1f} mm, rủi ro lũ cực đại {max_risk:.2f}. "
            f"Trạng thái đường bộ: {status_vi[road_status]}; trạng thái đường thủy: "
            f"{status_vi[water_status]}. Khi trạng thái là tạm ngưng, agent phải loại tuyến "
            "khỏi tập khả thi thay vì chỉ cộng penalty chi phí."
        )
        records.append(
            {
                "bulletin_id": f"WX_{date_value.strftime('%Y%m%d')}_{node_id}",
                "issued_at": iso_timestamp(pd.Timestamp(subset.iloc[0]["_time"])),
                "valid_from": iso_timestamp(pd.Timestamp(subset.iloc[0]["_time"])),
                "valid_to": iso_timestamp(pd.Timestamp(subset.iloc[-1]["_time"])),
                "node_id": str(node_id),
                "severity": severity,
                "road_status": road_status,
                "water_navigation_status": water_status,
                "max_rainfall_mm": max_rain,
                "max_flood_risk_idx": max_risk,
                "headline": headline,
                "bulletin_text": bulletin_text,
                "evidence_ref": f"weather:{date_value.isoformat()}:{node_id}",
                "source_type": "simulated",
            }
        )
    return normalize_frame("weather_bulletins", pd.DataFrame(records))


def generate_ops_notes(
    config: dict[str, Any],
    orders: pd.DataFrame,
    fleet: pd.DataFrame,
) -> pd.DataFrame:
    settings = config["grounding_generation"]["ops_notes"]
    start = pd.Timestamp(config["dataset"]["start"])
    end = pd.Timestamp(config["dataset"]["end"])
    records: list[dict[str, Any]] = []
    status_vi = {
        "available": "đang rảnh",
        "en_route": "đang chạy",
        "maintenance": "đang bảo trì",
        "reserved": "đã được đặt trước",
    }
    constraint = {
        "available": "NONE",
        "en_route": "VEHICLE_EN_ROUTE",
        "maintenance": "VEHICLE_MAINTENANCE",
        "reserved": "VEHICLE_RESERVED",
    }
    for row in fleet.itertuples(index=False):
        available_from = pd.Timestamp(row.available_from_ts)
        valid_until = max(
            available_from,
            start + pd.Timedelta(hours=float(settings["available_note_hours"])),
        )
        records.append(
            {
                "note_id": f"NOTE_{row.vehicle_id}",
                "created_at": iso_timestamp(start),
                "hub_id": row.current_node_id,
                "vehicle_id": row.vehicle_id,
                "note_type": "vehicle_status",
                "constraint_code": constraint[str(row.status)],
                "is_blocking": str(row.status) != "available" or available_from > start,
                "valid_until": iso_timestamp(valid_until),
                "note_text": (
                    f"{row.vehicle_id} ({row.vehicle_type}, tải {float(row.capacity_ton):g} tấn) "
                    f"{status_vi[str(row.status)]} tại {row.current_node_id}; mốc khả dụng dự kiến "
                    f"{row.available_from_ts}."
                ),
                "evidence_ref": f"fleet:{row.vehicle_id}",
                "source_type": "simulated",
            }
        )

    frame = orders.copy()
    frame["_arrival"] = pd.to_datetime(frame["arrival_ts"])
    frame["_date"] = frame["_arrival"].dt.floor("D")
    water_ok = {
        item["commodity_id"]: bool(item["water_ok"])
        for item in config["commodities"]
    }
    frame["_water_ok"] = frame["commodity_id"].map(water_ok).fillna(False)
    days = pd.date_range(start.floor("D"), end.floor("D"), freq="D")
    for day in days:
        for hub_id in sorted(config["order_generation"]["hubs"]):
            subset = frame.loc[(frame["_date"] == day) & (frame["hub_id"] == hub_id)]
            total_ton = float(subset["weight_kg"].sum() / 1000.0)
            water_ton = float(
                subset.loc[subset["_water_ok"], "weight_kg"].sum() / 1000.0
            )
            urgent = int((subset["priority_level"].astype(int) >= 4).sum())
            created = min(day + pd.Timedelta(hours=23), end)
            valid_until = created + pd.Timedelta(
                hours=float(settings["daily_note_valid_hours"])
            )
            records.append(
                {
                    "note_id": f"NOTE_INTAKE_{day.strftime('%Y%m%d')}_{hub_id}",
                    "created_at": iso_timestamp(created),
                    "hub_id": hub_id,
                    "vehicle_id": None,
                    "note_type": "daily_intake",
                    "constraint_code": "DEADLINE_PRESSURE" if urgent else "NONE",
                    "is_blocking": False,
                    "valid_until": iso_timestamp(valid_until),
                    "note_text": (
                        f"Ngày {day.date().isoformat()}, {hub_id} tiếp nhận {len(subset)} đơn, "
                        f"tổng {total_ton:.1f} tấn; {water_ton:.1f} tấn tương thích đường thủy; "
                        f"{urgent} đơn priority 4–5. Đây là ghi chú quan sát, không phải route recommendation."
                    ),
                    "evidence_ref": f"orders:{day.date().isoformat()}:{hub_id}",
                    "source_type": "simulated",
                }
            )
    records.sort(key=lambda row: (row["created_at"], row["note_id"]))
    return normalize_frame("ops_notes", pd.DataFrame(records))


def generate_policy_docs(config: dict[str, Any]) -> pd.DataFrame:
    effective_from = pd.Timestamp(config["dataset"]["start"]).date().isoformat()
    records = []
    for document in config["grounding_generation"]["policy_docs"]:
        row = dict(document)
        row["effective_from"] = row.get("effective_from", effective_from)
        records.append(row)
    return normalize_frame("policy_docs", pd.DataFrame(records))


def generate_tables(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    nodes = build_nodes(config)
    legs = build_legs(config, nodes)
    commodities = build_commodities(config)
    orders = generate_orders(config)
    weather = generate_weather(config, nodes)
    fleet = generate_fleet(config)
    fuel_prices = generate_fuel_prices(config)
    freight_rates = generate_freight_rates(config, legs, fuel_prices)
    tables = {
        "nodes": nodes,
        "legs": legs,
        "commodities": commodities,
        "orders": orders,
        "weather": weather,
        "fleet": fleet,
        "fuel_prices": fuel_prices,
        "freight_rates": freight_rates,
        "weather_bulletins": generate_weather_bulletins(config, nodes, weather),
        "ops_notes": generate_ops_notes(config, orders, fleet),
        "policy_docs": generate_policy_docs(config),
    }
    return {name: tables[name] for name in TABLE_ORDER}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_checksum(frame: pd.DataFrame) -> str:
    payload = frame.to_json(
        orient="records",
        force_ascii=False,
        double_precision=6,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json_records(frame: pd.DataFrame, path: Path) -> None:
    payload = frame.to_json(
        orient="records",
        force_ascii=False,
        double_precision=6,
    )
    path.write_text(payload + "\n", encoding="utf-8", newline="\n")


def build_compatibility_frames(
    config: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    settings = config["compatibility_exports"]
    node_names = dict(zip(tables["nodes"]["node_id"], tables["nodes"]["name_vi"]))
    commodity_codes = {
        row["commodity_id"]: row["compatibility_code_vi"]
        for row in config["commodities"]
    }
    orders = pd.DataFrame(
        {
            "hub_id": tables["orders"]["hub_id"],
            "hub_name": tables["orders"]["hub_id"].map(node_names),
            "timestamp": tables["orders"]["arrival_ts"],
            "loai_hang": tables["orders"]["commodity_id"].map(commodity_codes),
            "khoi_luong_kg": tables["orders"]["weight_kg"],
        }
    )
    weather = pd.DataFrame(
        {
            "region": tables["weather"]["node_id"].map(settings["location_codes"]),
            "timestamp": tables["weather"]["ts"],
            "canh_bao_mua_lu": tables["weather"]["alert_level"].map(
                settings["weather_alert_map"]
            ),
            "muc_nuoc_song_cm": tables["weather"]["river_level_m"] * 100.0,
        }
    )
    fleet = pd.DataFrame(
        {
            "vehicle_id": tables["fleet"]["vehicle_id"],
            "loai": tables["fleet"]["mode"].map(settings["fleet_type_map"]),
            "suc_chua_kg": tables["fleet"]["capacity_ton"] * 1000.0,
            "vi_tri_hien_tai": tables["fleet"]["current_node_id"].map(
                settings["location_codes"]
            ),
            "trang_thai": tables["fleet"]["status"].map(
                settings["fleet_status_map"]
            ),
        }
    )

    price_settings = settings["price_projection"]
    road_type = price_settings["reference_road_vehicle_type"]
    water_type = price_settings["reference_water_vehicle_type"]
    road_cost = float(
        tables["fleet"].loc[
            tables["fleet"]["vehicle_type"] == road_type, "cost_per_km_vnd"
        ].median()
    )
    water_cost = float(
        tables["fleet"].loc[
            tables["fleet"]["vehicle_type"] == water_type, "cost_per_km_vnd"
        ].median()
    )
    fuel_type = price_settings["road_fuel_type"]
    fuel = tables["fuel_prices"].loc[
        tables["fuel_prices"]["fuel_type"] == fuel_type,
        ["ts", "price_vnd_per_liter"],
    ].copy()
    fuel["_time"] = pd.to_datetime(fuel["ts"])
    fuel = fuel.sort_values("_time")
    demand = (
        tables["freight_rates"]
        .groupby(["ts", "mode"], sort=True, as_index=False)
        .agg(demand_idx=("demand_idx", "mean"), fuel_cost_factor=("fuel_cost_factor", "mean"))
    )
    demand["projection_idx"] = demand["demand_idx"] * demand["fuel_cost_factor"]
    pivot = demand.pivot(index="ts", columns="mode", values="projection_idx").reset_index()
    pivot["_time"] = pd.to_datetime(pivot["ts"])
    joined = pd.merge_asof(
        pivot.sort_values("_time"),
        fuel[["_time", "price_vnd_per_liter"]],
        on="_time",
        direction="backward",
    )
    price = pd.DataFrame(
        {
            "timestamp": joined["ts"],
            "gia_nhien_lieu_per_km": joined["price_vnd_per_liter"]
            * float(price_settings["road_fuel_liters_per_km"]),
            "gia_thue_xe_tai_per_km": road_cost * joined["road"],
            "gia_thue_sa_lan_per_km": water_cost * joined["water"],
        }
    )
    for frame in (orders, weather, fleet, price):
        for column in frame.select_dtypes(include=["float", "float32", "float64"]):
            frame[column] = frame[column].round(6)
    return {"orders": orders, "weather": weather, "fleet": fleet, "price": price}


def write_compatibility_outputs(
    config: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    output_dir: Path,
) -> dict[str, str]:
    settings = config["compatibility_exports"]
    if not settings.get("enabled", False):
        return {}
    compat_dir = output_dir / settings["directory_name"]
    compat_dir.mkdir(parents=True, exist_ok=True)
    frames = build_compatibility_frames(config, tables)
    checksums: dict[str, str] = {}
    for logical_name, frame in frames.items():
        filename = settings["filenames"][logical_name]
        path = compat_dir / filename
        _write_json_records(frame, path)
        checksums[filename] = sha256_file(path)
    return checksums


def write_stubs(
    config: dict[str, Any], tables: dict[str, pd.DataFrame], stubs_dir: Path
) -> None:
    stubs_dir.mkdir(parents=True, exist_ok=True)
    stub_tables = dict(tables)
    stub_tables["nodes"] = build_nodes(config, include_optional=True)
    for name in TABLE_ORDER:
        frame = stub_tables[name]
        if len(frame) < 10:
            raise ValueError(f"Cannot write {name} stub: only {len(frame)} rows available")
        frame.head(10).to_csv(
            stubs_dir / f"{name}.csv",
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.6f",
        )


def write_pack(
    config: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    output_dir: Path,
    output_format: str,
) -> dict[str, Any]:
    csv_dir = output_dir / "csv"
    json_dir = output_dir / "json"
    if output_format in ("csv", "both"):
        csv_dir.mkdir(parents=True, exist_ok=True)
    if output_format in ("json", "both"):
        json_dir.mkdir(parents=True, exist_ok=True)
    file_checksums: dict[str, str] = {}
    canonical_checksums: dict[str, str] = {}
    for name in TABLE_ORDER:
        frame = tables[name]
        canonical_checksums[name] = canonical_checksum(frame)
        if output_format in ("csv", "both"):
            path = csv_dir / f"{name}.csv"
            frame.to_csv(
                path,
                index=False,
                encoding="utf-8",
                lineterminator="\n",
                float_format="%.6f",
            )
            file_checksums[f"csv/{name}.csv"] = sha256_file(path)
        if output_format in ("json", "both"):
            path = json_dir / f"{name}.json"
            _write_json_records(frame, path)
            file_checksums[f"json/{name}.json"] = sha256_file(path)

    compatibility_checksums = write_compatibility_outputs(config, tables, output_dir)
    runtime_config_path = config.get("_runtime", {}).get("config_path", "")
    if runtime_config_path:
        try:
            runtime_config_path = Path(runtime_config_path).resolve().relative_to(
                Path.cwd().resolve()
            ).as_posix()
        except ValueError:
            runtime_config_path = Path(runtime_config_path).resolve().as_posix()
    metadata = {
        "dataset_version": str(config["dataset"]["version"]),
        "pack": config["dataset"]["pack"],
        "seed": int(config["dataset"]["seed"]),
        "config_path": runtime_config_path,
        "period": {
            "start": config["dataset"]["start"],
            "end": config["dataset"]["end"],
            "timezone": config["dataset"]["timezone"],
        },
        "frequencies": {
            "weather_hours": int(config["weather_generation"]["frequency_hours"]),
            "fuel_adjustment_days": int(
                config["fuel_generation"]["adjustment_interval_days"]
            ),
            "freight_hours": int(config["freight_generation"]["frequency_hours"]),
        },
        "row_counts": {name: int(len(tables[name])) for name in TABLE_ORDER},
        "file_checksums": file_checksums,
        "canonical_checksums": canonical_checksums,
        "scenario": copy.deepcopy(config["scenario"]),
        "compatibility_files": compatibility_checksums,
        "provenance_summary": {
            "verified": "No locally supplied numeric anchor was treated as verified.",
            "user_provided": "Selected provisional road distances from the execution contract.",
            "simulated": "Weather, orders, fleet state, prices, rates, water distances, and seasonality unless explicitly noted.",
        },
        "generated_at": config["dataset"]["generated_at"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return metadata


def generate_and_write(
    config_path: str | Path,
    seed_override: int | None = None,
    format_override: str | None = None,
    output_override: str | Path | None = None,
    create_stubs: bool = False,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], Path]:
    config = load_config(config_path)
    if seed_override is not None:
        config["dataset"]["seed"] = int(seed_override)
    output_format = format_override or config["dataset"]["default_format"]
    output_dir = (
        Path(output_override)
        if output_override is not None
        else Path(config["dataset"]["output_root"])
        / config["dataset"]["output_subdir"]
    )
    tables = generate_tables(config)
    metadata = write_pack(config, tables, output_dir, output_format)
    if create_stubs:
        write_stubs(config, tables, Path(config["dataset"]["stubs_dir"]))
    return tables, metadata, output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Base or scenario YAML config")
    parser.add_argument("--seed", type=int, help="Override dataset.seed")
    parser.add_argument(
        "--format",
        choices=("csv", "json", "both"),
        help="Override output format (compatibility JSON is always emitted)",
    )
    parser.add_argument(
        "--output-dir",
        help="Exact pack output directory; useful for tests/reproducibility checks",
    )
    parser.add_argument(
        "--write-stubs",
        action="store_true",
        help="Write 10-row CSV contract stubs to dataset.stubs_dir",
    )
    parser.add_argument(
        "--no-stubs",
        action="store_true",
        help="Do not auto-create stubs for the annual pack",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_preview = load_config(args.config)
    auto_stubs = (
        config_preview["dataset"]["pack"] == "annual"
        and args.output_dir is None
        and not args.no_stubs
    )
    _, metadata, output_dir = generate_and_write(
        args.config,
        seed_override=args.seed,
        format_override=args.format,
        output_override=args.output_dir,
        create_stubs=bool(args.write_stubs or auto_stubs),
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "pack": metadata["pack"],
                "output_dir": str(output_dir),
                "row_counts": metadata["row_counts"],
                "compatibility_files": sorted(metadata["compatibility_files"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
