#!/usr/bin/env python3
"""Hard validation for the VAIC semi-synthetic data packs.

The validator intentionally treats the CSV/JSON files as the public contract.
It does not import the generator, so generation and validation cannot silently
share an implementation bug.  Reproducibility is checked by invoking the
generator through its command line in a fresh temporary directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLE_NAMES = (
    "nodes",
    "legs",
    "commodities",
    "orders",
    "weather",
    "fleet",
    "fuel_prices",
    "freight_rates",
    "weather_bulletins",
    "ops_notes",
    "policy_docs",
)


@dataclass(frozen=True)
class ColumnRule:
    kind: str
    nullable: bool = False


# Dict insertion order is the frozen physical column order.
SCHEMAS: dict[str, dict[str, ColumnRule]] = {
    "nodes": {
        "node_id": ColumnRule("string"),
        "name_vi": ColumnRule("string"),
        "node_type": ColumnRule("string"),
        "location_label": ColumnRule("string"),
        "lat": ColumnRule("float"),
        "lon": ColumnRule("float"),
        "on_river": ColumnRule("bool"),
        "active": ColumnRule("bool"),
        "source_type": ColumnRule("string"),
    },
    "legs": {
        "leg_id": ColumnRule("string"),
        "from_node_id": ColumnRule("string"),
        "to_node_id": ColumnRule("string"),
        "mode": ColumnRule("string"),
        "distance_km": ColumnRule("float"),
        "duration_hr_base": ColumnRule("float"),
        "weather_sensitivity": ColumnRule("string"),
        "bidirectional": ColumnRule("bool"),
        "active": ColumnRule("bool"),
        "source_type": ColumnRule("string"),
        "source_note": ColumnRule("string"),
    },
    "commodities": {
        "commodity_id": ColumnRule("string"),
        "name_vi": ColumnRule("string"),
        "category": ColumnRule("string"),
        "perishability_level": ColumnRule("int"),
        "max_hold_hours": ColumnRule("float"),
        "loss_pct_per_hour": ColumnRule("float"),
        "value_vnd_per_kg": ColumnRule("float"),
        "needs_reefer": ColumnRule("bool"),
        "water_ok": ColumnRule("bool"),
        "compatible_vehicle_types": ColumnRule("string"),
        "source_type": ColumnRule("string"),
    },
    "orders": {
        "order_id": ColumnRule("string"),
        "hub_id": ColumnRule("string"),
        "commodity_id": ColumnRule("string"),
        "weight_kg": ColumnRule("float"),
        "arrival_ts": ColumnRule("datetime"),
        "ready_ts": ColumnRule("datetime"),
        "deadline_ts": ColumnRule("datetime"),
        "destination_node_id": ColumnRule("string"),
        "priority_level": ColumnRule("int"),
        "status": ColumnRule("string"),
    },
    "weather": {
        "ts": ColumnRule("datetime"),
        "node_id": ColumnRule("string"),
        "rainfall_mm": ColumnRule("float"),
        # Nullable only for nodes that do not participate in water transport.
        "river_level_m": ColumnRule("float", nullable=True),
        "flood_risk_idx": ColumnRule("float"),
        "road_factor": ColumnRule("float"),
        "water_factor": ColumnRule("float"),
        "alert_level": ColumnRule("string"),
    },
    "fleet": {
        "vehicle_id": ColumnRule("string"),
        "vehicle_type": ColumnRule("string"),
        "mode": ColumnRule("string"),
        "capacity_ton": ColumnRule("float"),
        "current_node_id": ColumnRule("string"),
        "status": ColumnRule("string"),
        "available_from_ts": ColumnRule("datetime"),
        "cost_fixed_vnd": ColumnRule("float"),
        "cost_per_km_vnd": ColumnRule("float"),
        "speed_kmh": ColumnRule("float"),
        "has_reefer": ColumnRule("bool"),
        "owner_hub_id": ColumnRule("string", nullable=True),
    },
    "fuel_prices": {
        "ts": ColumnRule("datetime"),
        "fuel_type": ColumnRule("string"),
        "price_vnd_per_liter": ColumnRule("float"),
        "adjustment_date": ColumnRule("date"),
        "source_type": ColumnRule("string"),
    },
    "freight_rates": {
        "ts": ColumnRule("datetime"),
        "mode": ColumnRule("string"),
        "leg_id": ColumnRule("string"),
        "vehicle_type": ColumnRule("string"),
        "fuel_type": ColumnRule("string"),
        "fuel_price_vnd_per_liter": ColumnRule("float"),
        "fuel_cost_factor": ColumnRule("float"),
        "rate_vnd_per_ton_km": ColumnRule("float"),
        "fixed_fee_vnd": ColumnRule("float"),
        "demand_idx": ColumnRule("float"),
        "rate_type": ColumnRule("string"),
    },
    "weather_bulletins": {
        "bulletin_id": ColumnRule("string"),
        "issued_at": ColumnRule("datetime"),
        "valid_from": ColumnRule("datetime"),
        "valid_to": ColumnRule("datetime"),
        "node_id": ColumnRule("string"),
        "severity": ColumnRule("string"),
        "road_status": ColumnRule("string"),
        "water_navigation_status": ColumnRule("string"),
        "max_rainfall_mm": ColumnRule("float"),
        "max_flood_risk_idx": ColumnRule("float"),
        "headline": ColumnRule("string"),
        "bulletin_text": ColumnRule("string"),
        "evidence_ref": ColumnRule("string"),
        "source_type": ColumnRule("string"),
    },
    "ops_notes": {
        "note_id": ColumnRule("string"),
        "created_at": ColumnRule("datetime"),
        "hub_id": ColumnRule("string"),
        "vehicle_id": ColumnRule("string", nullable=True),
        "note_type": ColumnRule("string"),
        "constraint_code": ColumnRule("string"),
        "is_blocking": ColumnRule("bool"),
        "valid_until": ColumnRule("datetime"),
        "note_text": ColumnRule("string"),
        "evidence_ref": ColumnRule("string"),
        "source_type": ColumnRule("string"),
    },
    "policy_docs": {
        "policy_id": ColumnRule("string"),
        "title": ColumnRule("string"),
        "effective_from": ColumnRule("date"),
        "applies_to": ColumnRule("string"),
        "policy_text": ColumnRule("string"),
        "citation_ref": ColumnRule("string"),
        "source_type": ColumnRule("string"),
    },
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "nodes": ("node_id",),
    "legs": ("leg_id",),
    "commodities": ("commodity_id",),
    "orders": ("order_id",),
    "weather": ("ts", "node_id"),
    "fleet": ("vehicle_id",),
    "fuel_prices": ("ts", "fuel_type"),
    "freight_rates": ("ts", "leg_id", "vehicle_type", "rate_type"),
    "weather_bulletins": ("bulletin_id",),
    "ops_notes": ("note_id",),
    "policy_docs": ("policy_id",),
}

ENUMS: dict[tuple[str, str], set[str]] = {
    ("nodes", "node_type"): {"farm_hub", "transshipment", "market"},
    ("nodes", "source_type"): {"verified", "user_provided", "assumption"},
    ("legs", "mode"): {"road", "water"},
    ("legs", "weather_sensitivity"): {"road_flood", "water_level", "mixed", "low"},
    ("legs", "source_type"): {"verified", "user_provided", "assumption"},
    ("commodities", "category"): {"grain", "fruit", "aquatic", "vegetable", "industrial_crop"},
    ("commodities", "source_type"): {"verified", "user_provided", "assumption"},
    ("orders", "status"): {"new", "ready", "cancelled"},
    ("weather", "alert_level"): {"none", "watch", "warning", "severe"},
    ("fleet", "vehicle_type"): {
        "truck_5t",
        "truck_15t",
        "reefer_8t",
        "boat_50t",
        "barge_200t",
        "barge_500t",
    },
    ("fleet", "mode"): {"road", "water"},
    ("fleet", "status"): {"available", "en_route", "maintenance", "reserved"},
    ("fuel_prices", "fuel_type"): {"diesel_005s", "gasoline", "marine_diesel"},
    ("fuel_prices", "source_type"): {"verified", "user_provided", "simulated"},
    ("freight_rates", "mode"): {"road", "water"},
    ("freight_rates", "rate_type"): {"spot", "contract"},
    ("freight_rates", "fuel_type"): {"diesel_005s", "marine_diesel"},
    ("weather_bulletins", "severity"): {"none", "watch", "warning", "severe"},
    ("weather_bulletins", "road_status"): {"open", "restricted", "closed"},
    ("weather_bulletins", "water_navigation_status"): {
        "open",
        "caution",
        "closed",
        "not_applicable",
    },
    ("weather_bulletins", "source_type"): {"simulated"},
    ("ops_notes", "note_type"): {"vehicle_status", "daily_intake"},
    ("ops_notes", "constraint_code"): {
        "NONE",
        "VEHICLE_EN_ROUTE",
        "VEHICLE_MAINTENANCE",
        "VEHICLE_RESERVED",
        "DEADLINE_PRESSURE",
    },
    ("ops_notes", "source_type"): {"simulated"},
    ("policy_docs", "source_type"): {"assumption", "user_provided", "verified"},
}

VEHICLE_MODES = {
    "truck_5t": "road",
    "truck_15t": "road",
    "reefer_8t": "road",
    "boat_50t": "water",
    "barge_200t": "water",
    "barge_500t": "water",
}

ASCII_ID = re.compile(r"^[A-Za-z0-9_-]+$")
HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MODEL_OUTPUT_COLUMNS = {
    "recommended_route",
    "predicted_cost",
    "selected_vehicle",
    "dispatch_decision",
}

EVAL_COLUMNS = (
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
)

COMPAT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "orders": ("hub_id", "hub_name", "timestamp", "loai_hang", "khoi_luong_kg"),
    "weather": ("region", "timestamp", "canh_bao_mua_lu", "muc_nuoc_song_cm"),
    "fleet": ("vehicle_id", "loai", "suc_chua_kg", "vi_tri_hien_tai", "trang_thai"),
    "price": (
        "timestamp",
        "gia_nhien_lieu_per_km",
        "gia_thue_xe_tai_per_km",
        "gia_thue_sa_lan_per_km",
    ),
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


class Reporter:
    def __init__(self, version: str, seed: int) -> None:
        self.payload: dict[str, Any] = {
            "status": "PASS",
            "dataset_version": version,
            "seed": seed,
            "checks_passed": 0,
            "checks_failed": 0,
            "row_counts": {},
            "file_checksums": {},
            "warnings": [],
            "errors": [],
            "checks": [],
            "generated_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="seconds"),
        }

    def check(
        self,
        name: str,
        condition: bool,
        message: str,
        *,
        details: Any | None = None,
        hard: bool = True,
    ) -> bool:
        passed = bool(condition)
        item: dict[str, Any] = {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "severity": "hard" if hard else "warning",
            "message": message,
        }
        if details is not None:
            item["details"] = _json_safe(details)
        self.payload["checks"].append(item)
        if passed:
            self.payload["checks_passed"] += 1
        elif hard:
            self.payload["checks_failed"] += 1
            self.payload["errors"].append(message)
            self.payload["status"] = "FAIL"
        else:
            self.payload["warnings"].append(message)
        return passed

    def warning(self, message: str) -> None:
        self.payload["warnings"].append(message)

    @property
    def failed(self) -> bool:
        return bool(self.payload["checks_failed"])

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_json_safe(self.payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


@dataclass
class Pack:
    name: str
    path: Path
    config_path: Path
    config: dict[str, Any]
    csv_raw: dict[str, pd.DataFrame] = field(default_factory=dict)
    json_raw: dict[str, pd.DataFrame] = field(default_factory=dict)
    csv_typed: dict[str, pd.DataFrame] = field(default_factory=dict)
    json_typed: dict[str, pd.DataFrame] = field(default_factory=dict)
    data_checksums: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] | None = None


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged = {key: value for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else value
        return merged
    return override


def load_config(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    path = path.resolve()
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError(f"Cyclic YAML extends chain at {path}")
    seen.add(path)
    content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(content, dict):
        raise ValueError(f"Config must contain a mapping: {path}")
    parent_ref = content.pop("extends", None)
    if parent_ref is None:
        return content
    parent_path = (path.parent / str(parent_ref)).resolve()
    return _deep_merge(load_config(parent_path, seen), content)


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _expected_offset(config: Mapping[str, Any]) -> str:
    return str(config.get("validation", {}).get("allowed_timestamp_offset", "+07:00"))


def _parse_datetime(value: Any, expected_offset: str) -> datetime | None:
    if not isinstance(value, str) or "T" not in value or not value.endswith(expected_offset):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    sign = "+" if parsed.utcoffset() >= timedelta(0) else "-"
    total_minutes = abs(int(parsed.utcoffset().total_seconds() // 60))
    actual_offset = f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    return parsed if actual_offset == expected_offset else None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or DATE_TEXT.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


def coerce_table(
    frame: pd.DataFrame,
    schema: Mapping[str, ColumnRule],
    expected_offset: str,
) -> tuple[pd.DataFrame, list[str]]:
    converted = pd.DataFrame(index=frame.index)
    errors: list[str] = []
    for column, rule in schema.items():
        if column not in frame.columns:
            errors.append(f"missing column {column}")
            continue
        source = frame[column]
        missing = source.map(_is_missing)
        if not rule.nullable and bool(missing.any()):
            sample = source.index[missing].tolist()[:5]
            errors.append(f"{column}: {int(missing.sum())} required null/blank value(s), rows {sample}")

        if rule.kind == "string":
            values = source.map(lambda value: None if _is_missing(value) else str(value))
            converted[column] = values
            continue

        if rule.kind in {"float", "int"}:
            numeric_source = source.mask(missing, np.nan)
            numeric = pd.to_numeric(numeric_source, errors="coerce")
            invalid = (~missing) & numeric.isna()
            if bool(invalid.any()):
                samples = source[invalid].astype(str).head(5).tolist()
                errors.append(f"{column}: non-numeric value(s) {samples}")
            if rule.kind == "int":
                non_integral = numeric.notna() & ~np.isclose(numeric, np.round(numeric), atol=1e-12)
                if bool(non_integral.any()):
                    samples = source[non_integral].astype(str).head(5).tolist()
                    errors.append(f"{column}: non-integral value(s) {samples}")
                numeric = numeric.map(lambda value: int(round(value)) if pd.notna(value) else np.nan)
            converted[column] = numeric
            continue

        if rule.kind == "bool":
            values = source.map(lambda value: None if _is_missing(value) else _parse_bool(value))
            invalid = (~missing) & values.isna()
            if bool(invalid.any()):
                samples = source[invalid].astype(str).head(5).tolist()
                errors.append(f"{column}: invalid boolean value(s) {samples}")
            converted[column] = values
            continue

        if rule.kind == "datetime":
            values = source.map(
                lambda value: None if _is_missing(value) else _parse_datetime(value, expected_offset)
            )
            invalid = (~missing) & values.isna()
            if bool(invalid.any()):
                samples = source[invalid].astype(str).head(5).tolist()
                errors.append(
                    f"{column}: invalid ISO-8601 timestamp or offset (expected {expected_offset}): {samples}"
                )
            converted[column] = values
            continue

        if rule.kind == "date":
            values = source.map(lambda value: None if _is_missing(value) else _parse_date(value))
            invalid = (~missing) & values.isna()
            if bool(invalid.any()):
                samples = source[invalid].astype(str).head(5).tolist()
                errors.append(f"{column}: invalid ISO date value(s) {samples}")
            converted[column] = values
            continue

        errors.append(f"{column}: unknown schema kind {rule.kind}")
    return converted, errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack_digest(checksums: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(checksums):
        if not (relative_path.startswith("csv/") or relative_path.startswith("json/")):
            continue
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(checksums[relative_path].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=object, keep_default_na=False, encoding="utf-8")


def _read_json_records(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(record, dict) for record in payload):
        raise ValueError("top-level JSON value must be an array of objects")
    return pd.DataFrame(payload)


def _frame_equivalent(
    left: pd.DataFrame,
    right: pd.DataFrame,
    table: str,
    tolerance: float,
) -> tuple[bool, str]:
    columns = list(SCHEMAS[table])
    if list(left.columns) != columns or list(right.columns) != columns:
        return False, "typed frames do not both have the exact schema"
    if len(left) != len(right):
        return False, f"row count differs: CSV={len(left)}, JSON={len(right)}"

    # The physical order should already match, but comparison is deliberately
    # order-independent so harmless serialization ordering cannot hide data QA.
    sort_columns = list(PRIMARY_KEYS[table])
    try:
        left_order = left.assign(
            __sort_key=left[sort_columns].astype(str).agg("\x1f".join, axis=1)
        ).sort_values("__sort_key", kind="mergesort").drop(columns="__sort_key").reset_index(drop=True)
        right_order = right.assign(
            __sort_key=right[sort_columns].astype(str).agg("\x1f".join, axis=1)
        ).sort_values("__sort_key", kind="mergesort").drop(columns="__sort_key").reset_index(drop=True)
    except Exception as exc:  # pragma: no cover - defensive for malformed frames
        return False, f"could not align rows by key: {exc}"

    mismatches: list[str] = []
    for column, rule in SCHEMAS[table].items():
        lhs = left_order[column]
        rhs = right_order[column]
        if rule.kind == "float":
            lhs_values = pd.to_numeric(lhs, errors="coerce").to_numpy(dtype=float)
            rhs_values = pd.to_numeric(rhs, errors="coerce").to_numpy(dtype=float)
            equal = np.isclose(lhs_values, rhs_values, rtol=tolerance, atol=tolerance, equal_nan=True)
        else:
            equal = np.fromiter(
                (
                    (_is_missing(a) and _is_missing(b))
                    or (not _is_missing(a) and not _is_missing(b) and a == b)
                    for a, b in zip(lhs.to_numpy(dtype=object), rhs.to_numpy(dtype=object))
                ),
                dtype=bool,
                count=len(lhs),
            )
        if not bool(equal.all()):
            indices = np.flatnonzero(~equal)[:3].tolist()
            mismatches.append(f"{column} at aligned row(s) {indices}")
    if mismatches:
        return False, "; ".join(mismatches[:5])
    return True, "CSV and JSON contain equivalent records"


def _actual_data_files(pack_path: Path, compat_names: Iterable[str]) -> list[Path]:
    paths = [pack_path / "csv" / f"{table}.csv" for table in TABLE_NAMES]
    paths += [pack_path / "json" / f"{table}.json" for table in TABLE_NAMES]
    paths += [pack_path / "compat" / filename for filename in compat_names]
    return paths


def _flatten_checksum_mapping(value: Any, prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    if not isinstance(value, Mapping):
        return flattened
    for key, item in value.items():
        normalized_key = str(key).replace("\\", "/").strip("/")
        joined = "/".join(part for part in (prefix, normalized_key) if part)
        if isinstance(item, str):
            flattened[joined] = item
        elif isinstance(item, Mapping) and isinstance(item.get("sha256"), str):
            flattened[joined] = str(item["sha256"])
        elif isinstance(item, Mapping):
            flattened.update(_flatten_checksum_mapping(item, joined))
    return flattened


def _metadata_checksum_map(metadata: Mapping[str, Any]) -> dict[str, str]:
    source = metadata.get("file_checksums")
    if source is None:
        source = metadata.get("checksums")
    return _flatten_checksum_mapping(source)


def _lookup_metadata_checksum(checksums: Mapping[str, str], relative_path: str) -> str | None:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    if normalized in checksums:
        return checksums[normalized]
    # Allow a generator to prefix entries with the pack path while retaining an
    # unambiguous relative suffix.
    matches = [value for key, value in checksums.items() if key.endswith("/" + normalized)]
    return matches[0] if len(matches) == 1 else None


def _validate_metadata(pack: Pack, reporter: Reporter, expected_files: Sequence[Path]) -> None:
    metadata_path = pack.path / "metadata.json"
    if not reporter.check(
        f"{pack.name}.metadata.exists",
        metadata_path.is_file(),
        f"{pack.name}: metadata.json exists",
    ):
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("metadata root must be an object")
        pack.metadata = metadata
    except Exception as exc:
        reporter.check(
            f"{pack.name}.metadata.parse",
            False,
            f"{pack.name}: metadata.json is not valid UTF-8 JSON: {exc}",
        )
        return

    dataset_cfg = pack.config.get("dataset", {})
    expected_version = str(dataset_cfg.get("version", "2.0"))
    expected_seed = int(dataset_cfg.get("seed", 20260717))
    expected_pack = str(dataset_cfg.get("pack", pack.name))
    expected_timezone = str(dataset_cfg.get("timezone", "Asia/Bangkok"))
    period = metadata.get("period", {})

    identity_ok = (
        str(metadata.get("dataset_version", metadata.get("version", ""))) == expected_version
        and int(metadata.get("seed", -1)) == expected_seed
        and str(metadata.get("pack", "")) == expected_pack
        and isinstance(period, Mapping)
        and str(period.get("timezone", "")) == expected_timezone
        and str(period.get("start", "")) == str(dataset_cfg.get("start", ""))
        and str(period.get("end", "")) == str(dataset_cfg.get("end", ""))
    )
    reporter.check(
        f"{pack.name}.metadata.identity",
        identity_ok,
        f"{pack.name}: metadata version/seed/pack/timezone/window match the resolved config",
        details={
            "metadata": {
                key: metadata.get(key)
                for key in ("dataset_version", "version", "seed", "pack")
            },
            "period": period,
            "expected_pack": expected_pack,
        },
    )

    config_path_value = metadata.get("config_path")
    config_path_ok = False
    if isinstance(config_path_value, str) and config_path_value:
        declared_config_path = Path(config_path_value)
        if not declared_config_path.is_absolute():
            declared_config_path = PROJECT_ROOT / declared_config_path
        config_path_ok = declared_config_path.resolve() == pack.config_path.resolve()
    reporter.check(
        f"{pack.name}.metadata.config_path",
        config_path_ok,
        f"{pack.name}: metadata config_path identifies the resolved pack config",
        details={"metadata": config_path_value, "expected_filename": pack.config_path.name},
    )

    frequencies = metadata.get("frequencies", {})
    expected_frequencies = {
        "weather_hours": int(pack.config.get("weather_generation", {}).get("frequency_hours", 1)),
        "fuel_adjustment_days": int(pack.config.get("fuel_generation", {}).get("adjustment_interval_days", 14)),
        "freight_hours": int(pack.config.get("freight_generation", {}).get("frequency_hours", 6)),
    }
    frequencies_ok = isinstance(frequencies, Mapping) and all(
        key in frequencies and int(frequencies[key]) == value
        for key, value in expected_frequencies.items()
    )
    reporter.check(
        f"{pack.name}.metadata.frequencies",
        frequencies_ok,
        f"{pack.name}: metadata frequencies match generator configuration",
        details={"metadata": frequencies, "expected": expected_frequencies},
    )

    reporter.check(
        f"{pack.name}.metadata.scenario",
        metadata.get("scenario") == pack.config.get("scenario", {}),
        f"{pack.name}: metadata embeds the full resolved scenario configuration",
    )

    generated_at = metadata.get("generated_at")
    generated_at_ok = (
        _parse_datetime(generated_at, _expected_offset(pack.config)) is not None
        and generated_at == dataset_cfg.get("generated_at")
    )
    reporter.check(
        f"{pack.name}.metadata.generated_at",
        generated_at_ok,
        f"{pack.name}: metadata generated_at is the deterministic ISO-8601 config value",
    )

    row_counts = metadata.get("row_counts")
    expected_counts = {table: len(pack.csv_raw[table]) for table in TABLE_NAMES if table in pack.csv_raw}
    row_counts_ok = isinstance(row_counts, Mapping) and all(
        table in row_counts and int(row_counts[table]) == count
        for table, count in expected_counts.items()
    )
    reporter.check(
        f"{pack.name}.metadata.row_counts",
        row_counts_ok and len(expected_counts) == len(TABLE_NAMES),
        f"{pack.name}: metadata row_counts match all {len(TABLE_NAMES)} canonical CSV tables",
        details={"expected": expected_counts, "metadata": row_counts},
    )

    checksum_map = _metadata_checksum_map(metadata)
    checksum_shape_ok = bool(checksum_map) and all(HEX_SHA256.fullmatch(value) for value in checksum_map.values())
    reporter.check(
        f"{pack.name}.metadata.checksum_format",
        checksum_shape_ok,
        f"{pack.name}: metadata contains valid SHA-256 file checksums",
        details={"checksum_entries": len(checksum_map)},
    )

    canonical_files = [
        path
        for path in expected_files
        if path.is_file()
        and path.relative_to(pack.path).as_posix().split("/", 1)[0] in {"csv", "json"}
    ]
    mismatches: list[str] = []
    missing: list[str] = []
    for path in canonical_files:
        if not path.is_file():
            continue
        relative = path.relative_to(pack.path).as_posix()
        declared = _lookup_metadata_checksum(checksum_map, relative)
        if declared is None:
            missing.append(relative)
        elif declared.lower() != sha256_file(path):
            mismatches.append(relative)
    reporter.check(
        f"{pack.name}.metadata.checksums_match",
        not missing and not mismatches,
        f"{pack.name}: metadata file_checksums cover and match every canonical CSV/JSON file",
        details={"missing_entries": missing, "mismatched_entries": mismatches},
    )

    canonical_checksums = metadata.get("canonical_checksums")
    canonical_mismatches: list[str] = []
    canonical_missing: list[str] = []
    if not isinstance(canonical_checksums, Mapping):
        canonical_missing = list(TABLE_NAMES)
    else:
        for table in TABLE_NAMES:
            declared = canonical_checksums.get(table)
            json_path = pack.path / "json" / f"{table}.json"
            if not isinstance(declared, str) or HEX_SHA256.fullmatch(declared) is None:
                canonical_missing.append(table)
                continue
            if json_path.is_file():
                # The canonical representation is the compact records JSON;
                # the physical JSON export adds exactly one trailing newline.
                payload = json_path.read_bytes()
                if payload.endswith(b"\n"):
                    payload = payload[:-1]
                actual = hashlib.sha256(payload).hexdigest()
                if declared.lower() != actual:
                    canonical_mismatches.append(table)
    canonical_checksum_ok = not canonical_missing and not canonical_mismatches
    reporter.check(
        f"{pack.name}.metadata.canonical_checksums",
        canonical_checksum_ok,
        f"{pack.name}: metadata canonical checksums match the compact JSON representation of every table",
        details={"missing": canonical_missing, "mismatched": canonical_mismatches},
    )

    compatibility_files = metadata.get("compatibility_files")
    compat_paths = [
        path
        for path in expected_files
        if path.is_file() and path.relative_to(pack.path).as_posix().startswith("compat/")
    ]
    compat_missing: list[str] = []
    compat_mismatch: list[str] = []
    if not isinstance(compatibility_files, Mapping):
        compat_missing = [path.name for path in compat_paths]
    else:
        for path in compat_paths:
            declared = compatibility_files.get(path.name)
            if not isinstance(declared, str):
                compat_missing.append(path.name)
            elif declared.lower() != sha256_file(path):
                compat_mismatch.append(path.name)
    reporter.check(
        f"{pack.name}.metadata.compatibility_checksums",
        not compat_missing and not compat_mismatch and bool(compat_paths),
        f"{pack.name}: metadata compatibility_files checksums cover and match all four handoff JSON files",
        details={"missing_entries": compat_missing, "mismatched_entries": compat_mismatch},
    )


def _validate_compatibility_exports(pack: Pack, reporter: Reporter) -> list[str]:
    compat_cfg = pack.config.get("compatibility_exports", {})
    if not compat_cfg.get("enabled", False):
        reporter.check(
            f"{pack.name}.compat.enabled",
            False,
            f"{pack.name}: compatibility exports are enabled by the base config",
        )
        return []

    filenames = compat_cfg.get("filenames", {})
    expected_filenames: list[str] = []
    records_by_kind: dict[str, list[dict[str, Any]]] = {}
    for kind, columns in COMPAT_SCHEMAS.items():
        filename = filenames.get(kind)
        if not isinstance(filename, str) or not filename:
            reporter.check(
                f"{pack.name}.compat.{kind}.filename",
                False,
                f"{pack.name}: compatibility filename for {kind} is configured",
            )
            continue
        expected_filenames.append(filename)
        path = pack.path / str(compat_cfg.get("directory_name", "compat")) / filename
        if not reporter.check(
            f"{pack.name}.compat.{kind}.exists",
            path.is_file(),
            f"{pack.name}: {path.relative_to(pack.path).as_posix()} exists",
        ):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            valid_records = isinstance(payload, list) and all(isinstance(row, dict) for row in payload)
            if not valid_records:
                raise ValueError("top-level value must be an array of objects")
            records = payload
            records_by_kind[kind] = records
        except Exception as exc:
            reporter.check(
                f"{pack.name}.compat.{kind}.parse",
                False,
                f"{pack.name}: {filename} is not a valid JSON records array: {exc}",
            )
            continue

        exact_schema = bool(records) and all(tuple(row.keys()) == columns for row in records)
        reporter.check(
            f"{pack.name}.compat.{kind}.schema",
            exact_schema,
            f"{pack.name}: {filename} has the exact compatibility schema",
            details={"expected_columns": columns, "rows": len(records)},
        )

    expected_offset = _expected_offset(pack.config)
    orders = records_by_kind.get("orders", [])
    allowed_hubs = set(pack.csv_typed.get("nodes", pd.DataFrame()).get("node_id", pd.Series(dtype=object)).dropna())
    commodity_codes = {
        str(item.get("compatibility_code_vi"))
        for item in pack.config.get("commodities", [])
        if item.get("compatibility_code_vi")
    }
    orders_ok = bool(orders) and all(
        row.get("hub_id") in allowed_hubs
        and isinstance(row.get("hub_name"), str)
        and bool(row["hub_name"].strip())
        and _parse_datetime(row.get("timestamp"), expected_offset) is not None
        and row.get("loai_hang") in commodity_codes
        and isinstance(row.get("khoi_luong_kg"), (int, float))
        and not isinstance(row.get("khoi_luong_kg"), bool)
        and float(row["khoi_luong_kg"]) > 0
        for row in orders
    )
    if orders:
        canonical_orders = pack.csv_typed.get("orders")
        count_and_total_ok = canonical_orders is not None and len(orders) == len(canonical_orders)
        if count_and_total_ok:
            compat_total = sum(float(row["khoi_luong_kg"]) for row in orders)
            canonical_total = float(canonical_orders["weight_kg"].sum())
            tolerance = float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6))
            count_and_total_ok = math.isclose(
                compat_total,
                canonical_total,
                rel_tol=tolerance,
                abs_tol=tolerance,
            )
        orders_ok = orders_ok and count_and_total_ok
    reporter.check(
        f"{pack.name}.compat.orders.values",
        orders_ok,
        f"{pack.name}: compatibility orders are valid and reconcile to canonical count/weight",
    )

    weather = records_by_kind.get("weather", [])
    allowed_regions = set(compat_cfg.get("location_codes", {}).values())
    allowed_alerts = set(compat_cfg.get("weather_alert_map", {}).values())
    weather_ok = bool(weather) and all(
        row.get("region") in allowed_regions
        and _parse_datetime(row.get("timestamp"), expected_offset) is not None
        and row.get("canh_bao_mua_lu") in allowed_alerts
        and (
            row.get("muc_nuoc_song_cm") is None
            or (
                isinstance(row.get("muc_nuoc_song_cm"), (int, float))
                and not isinstance(row.get("muc_nuoc_song_cm"), bool)
                and math.isfinite(float(row["muc_nuoc_song_cm"]))
            )
        )
        for row in weather
    )
    if weather:
        canonical_weather = pack.csv_typed.get("weather")
        weather_ok = weather_ok and canonical_weather is not None and len(weather) == len(canonical_weather)
    reporter.check(
        f"{pack.name}.compat.weather.values",
        weather_ok,
        f"{pack.name}: compatibility weather values are valid and row count reconciles",
    )

    fleet = records_by_kind.get("fleet", [])
    fleet_ok = bool(fleet) and all(
        isinstance(row.get("vehicle_id"), str)
        and row.get("loai") in set(compat_cfg.get("fleet_type_map", {}).values())
        and isinstance(row.get("suc_chua_kg"), (int, float))
        and not isinstance(row.get("suc_chua_kg"), bool)
        and float(row["suc_chua_kg"]) > 0
        and row.get("vi_tri_hien_tai") in allowed_regions
        and row.get("trang_thai") in set(compat_cfg.get("fleet_status_map", {}).values())
        for row in fleet
    )
    if fleet:
        canonical_fleet = pack.csv_typed.get("fleet")
        fleet_ok = fleet_ok and canonical_fleet is not None and len(fleet) == len(canonical_fleet)
    reporter.check(
        f"{pack.name}.compat.fleet.values",
        fleet_ok,
        f"{pack.name}: compatibility fleet values are valid and row count reconciles",
    )

    prices = records_by_kind.get("price", [])
    price_ok = bool(prices) and all(
        _parse_datetime(row.get("timestamp"), expected_offset) is not None
        and all(
            isinstance(row.get(column), (int, float))
            and not isinstance(row.get(column), bool)
            and math.isfinite(float(row[column]))
            and float(row[column]) > 0
            for column in COMPAT_SCHEMAS["price"][1:]
        )
        for row in prices
    )
    reporter.check(
        f"{pack.name}.compat.price.values",
        price_ok,
        f"{pack.name}: compatibility price records contain positive finite values",
    )
    return expected_filenames


def _validate_pack_files(pack: Pack, reporter: Reporter) -> None:
    expected_csv = {f"{table}.csv" for table in TABLE_NAMES}
    expected_json = {f"{table}.json" for table in TABLE_NAMES}
    actual_csv = {path.name for path in (pack.path / "csv").glob("*.csv")} if (pack.path / "csv").is_dir() else set()
    actual_json = {path.name for path in (pack.path / "json").glob("*.json")} if (pack.path / "json").is_dir() else set()
    reporter.check(
        f"{pack.name}.files.csv_set",
        actual_csv == expected_csv,
        f"{pack.name}: csv/ contains exactly the {len(TABLE_NAMES)} canonical CSV files",
        details={"missing": expected_csv - actual_csv, "extra": actual_csv - expected_csv},
    )
    reporter.check(
        f"{pack.name}.files.json_set",
        actual_json == expected_json,
        f"{pack.name}: json/ contains exactly the {len(TABLE_NAMES)} canonical JSON files",
        details={"missing": expected_json - actual_json, "extra": actual_json - expected_json},
    )

    expected_offset = _expected_offset(pack.config)
    tolerance = float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6))
    row_counts: dict[str, int] = {}
    checksums: dict[str, str] = {}
    for table in TABLE_NAMES:
        csv_path = pack.path / "csv" / f"{table}.csv"
        json_path = pack.path / "json" / f"{table}.json"
        for path in (csv_path, json_path):
            if path.is_file():
                checksums[path.relative_to(pack.path).as_posix()] = sha256_file(path)

        if not csv_path.is_file() or not json_path.is_file():
            continue
        try:
            csv_frame = _read_csv(csv_path)
            pack.csv_raw[table] = csv_frame
        except Exception as exc:
            reporter.check(
                f"{pack.name}.{table}.csv_parse",
                False,
                f"{pack.name}/{table}: CSV cannot be parsed as UTF-8: {exc}",
            )
            continue
        try:
            json_frame = _read_json_records(json_path)
            pack.json_raw[table] = json_frame
        except Exception as exc:
            reporter.check(
                f"{pack.name}.{table}.json_parse",
                False,
                f"{pack.name}/{table}: JSON cannot be parsed as UTF-8 records: {exc}",
            )
            continue

        expected_columns = list(SCHEMAS[table])
        csv_schema_ok = list(csv_frame.columns) == expected_columns
        json_schema_ok = list(json_frame.columns) == expected_columns
        reporter.check(
            f"{pack.name}.{table}.schema.csv",
            csv_schema_ok,
            f"{pack.name}/{table}: CSV has the exact frozen schema and column order",
            details={"expected": expected_columns, "actual": list(csv_frame.columns)},
        )
        reporter.check(
            f"{pack.name}.{table}.schema.json",
            json_schema_ok,
            f"{pack.name}/{table}: JSON has the exact frozen schema and field order",
            details={"expected": expected_columns, "actual": list(json_frame.columns)},
        )
        extra_model_columns = (set(csv_frame.columns) | set(json_frame.columns)) & MODEL_OUTPUT_COLUMNS
        reporter.check(
            f"{pack.name}.{table}.no_model_outputs",
            not extra_model_columns,
            f"{pack.name}/{table}: no optimizer/dispatch output columns are mixed into input data",
            details={"forbidden_columns": extra_model_columns},
        )

        if csv_schema_ok:
            csv_typed, csv_errors = coerce_table(csv_frame, SCHEMAS[table], expected_offset)
            pack.csv_typed[table] = csv_typed
            reporter.check(
                f"{pack.name}.{table}.types.csv",
                not csv_errors,
                f"{pack.name}/{table}: all CSV fields parse and required fields are non-null",
                details={"errors": csv_errors[:20]},
            )
        if json_schema_ok:
            json_typed, json_errors = coerce_table(json_frame, SCHEMAS[table], expected_offset)
            pack.json_typed[table] = json_typed
            reporter.check(
                f"{pack.name}.{table}.types.json",
                not json_errors,
                f"{pack.name}/{table}: all JSON fields parse and required fields are non-null",
                details={"errors": json_errors[:20]},
            )

        if table in pack.csv_typed and table in pack.json_typed:
            equivalent, reason = _frame_equivalent(
                pack.csv_typed[table], pack.json_typed[table], table, tolerance
            )
            reporter.check(
                f"{pack.name}.{table}.csv_json_equivalent",
                equivalent,
                f"{pack.name}/{table}: {reason}",
            )
        row_counts[table] = len(csv_frame)

    pack.data_checksums.update(checksums)
    reporter.payload["row_counts"][pack.name] = row_counts
    reporter.payload["file_checksums"][pack.name] = dict(checksums)


def _series_in_range(series: pd.Series, lower: float | None, upper: float | None, *, strict_lower: bool = False) -> bool:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric.astype(float)).all():
        return False
    condition = pd.Series(True, index=numeric.index)
    if lower is not None:
        condition &= numeric > lower if strict_lower else numeric >= lower
    if upper is not None:
        condition &= numeric <= upper
    return bool(condition.all())


def _validate_keys_and_domains(pack: Pack, reporter: Reporter) -> None:
    frames = pack.csv_typed
    if set(frames) != set(TABLE_NAMES):
        reporter.check(
            f"{pack.name}.domain.precondition",
            False,
            f"{pack.name}: domain checks require all {len(TABLE_NAMES)} parseable CSV tables",
        )
        return

    for table, keys in PRIMARY_KEYS.items():
        frame = frames[table]
        unique = not frame.duplicated(list(keys), keep=False).any()
        reporter.check(
            f"{pack.name}.{table}.primary_key",
            unique,
            f"{pack.name}/{table}: primary key {list(keys)} is unique",
            details={"duplicate_rows": int(frame.duplicated(list(keys), keep=False).sum())},
        )

    id_columns = {
        "nodes": ("node_id",),
        "legs": ("leg_id", "from_node_id", "to_node_id"),
        "commodities": ("commodity_id",),
        "orders": ("order_id", "hub_id", "commodity_id", "destination_node_id"),
        "weather": ("node_id",),
        "fleet": ("vehicle_id", "current_node_id"),
        "freight_rates": ("leg_id",),
        "weather_bulletins": ("bulletin_id", "node_id"),
        "ops_notes": ("note_id", "hub_id"),
        "policy_docs": ("policy_id",),
    }
    ascii_bad: list[str] = []
    for table, columns in id_columns.items():
        for column in columns:
            invalid = frames[table][column].dropna().map(lambda value: ASCII_ID.fullmatch(str(value)) is None)
            if bool(invalid.any()):
                ascii_bad.append(f"{table}.{column}")
    owner_invalid = frames["fleet"]["owner_hub_id"].dropna().map(
        lambda value: ASCII_ID.fullmatch(str(value)) is None
    )
    if bool(owner_invalid.any()):
        ascii_bad.append("fleet.owner_hub_id")
    ops_vehicle_invalid = frames["ops_notes"]["vehicle_id"].dropna().map(
        lambda value: ASCII_ID.fullmatch(str(value)) is None
    )
    if bool(ops_vehicle_invalid.any()):
        ascii_bad.append("ops_notes.vehicle_id")
    reporter.check(
        f"{pack.name}.keys.ascii",
        not ascii_bad,
        f"{pack.name}: all IDs and keys use ASCII-safe characters",
        details={"invalid_columns": ascii_bad},
    )

    enum_errors: dict[str, list[str]] = {}
    for (table, column), allowed in ENUMS.items():
        actual = {str(value) for value in frames[table][column].dropna().unique()}
        invalid = sorted(actual - allowed)
        if invalid:
            enum_errors[f"{table}.{column}"] = invalid
    reporter.check(
        f"{pack.name}.enums",
        not enum_errors,
        f"{pack.name}: all enum fields use allowed contract values",
        details=enum_errors,
    )

    node_ids = set(frames["nodes"]["node_id"].dropna())
    commodity_ids = set(frames["commodities"]["commodity_id"].dropna())
    leg_ids = set(frames["legs"]["leg_id"].dropna())
    vehicle_ids = set(frames["fleet"]["vehicle_id"].dropna())
    fk_errors: dict[str, list[str]] = {}

    def check_fk(label: str, values: pd.Series, parents: set[Any], nullable: bool = False) -> None:
        candidates = values.dropna() if nullable else values
        missing = sorted({str(value) for value in candidates if value not in parents})
        if missing:
            fk_errors[label] = missing[:20]

    check_fk("legs.from_node_id", frames["legs"]["from_node_id"], node_ids)
    check_fk("legs.to_node_id", frames["legs"]["to_node_id"], node_ids)
    check_fk("orders.hub_id", frames["orders"]["hub_id"], node_ids)
    check_fk("orders.destination_node_id", frames["orders"]["destination_node_id"], node_ids)
    check_fk("orders.commodity_id", frames["orders"]["commodity_id"], commodity_ids)
    check_fk("weather.node_id", frames["weather"]["node_id"], node_ids)
    check_fk("fleet.current_node_id", frames["fleet"]["current_node_id"], node_ids)
    check_fk("fleet.owner_hub_id", frames["fleet"]["owner_hub_id"], node_ids, nullable=True)
    check_fk("freight_rates.leg_id", frames["freight_rates"]["leg_id"], leg_ids)
    check_fk("weather_bulletins.node_id", frames["weather_bulletins"]["node_id"], node_ids)
    check_fk("ops_notes.hub_id", frames["ops_notes"]["hub_id"], node_ids)
    check_fk("ops_notes.vehicle_id", frames["ops_notes"]["vehicle_id"], vehicle_ids, nullable=True)
    reporter.check(
        f"{pack.name}.foreign_keys",
        not fk_errors,
        f"{pack.name}: all foreign keys resolve without orphans",
        details=fk_errors,
    )

    farm_hubs = set(frames["nodes"].loc[frames["nodes"]["node_type"] == "farm_hub", "node_id"])
    reporter.check(
        f"{pack.name}.orders.hub_is_farm_hub",
        set(frames["orders"]["hub_id"].dropna()).issubset(farm_hubs),
        f"{pack.name}/orders: every hub_id refers to a farm_hub node",
    )

    compatible_errors: list[str] = []
    known_vehicle_types = set(VEHICLE_MODES)
    for commodity_id, value in frames["commodities"][["commodity_id", "compatible_vehicle_types"]].itertuples(index=False):
        types = {part.strip() for part in str(value).split("|") if part.strip()}
        if not types or not types.issubset(known_vehicle_types):
            compatible_errors.append(str(commodity_id))
    reporter.check(
        f"{pack.name}.commodities.vehicle_compatibility",
        not compatible_errors,
        f"{pack.name}/commodities: compatible_vehicle_types contains only known, non-empty values",
        details={"invalid_commodity_ids": compatible_errors},
    )

    fleet_mode_errors = frames["fleet"].apply(
        lambda row: VEHICLE_MODES.get(row["vehicle_type"]) != row["mode"], axis=1
    )
    leg_modes = frames["legs"].set_index("leg_id")["mode"].to_dict()
    freight_mode_errors = frames["freight_rates"].apply(
        lambda row: (
            VEHICLE_MODES.get(row["vehicle_type"]) != row["mode"]
            or leg_modes.get(row["leg_id"]) != row["mode"]
        ),
        axis=1,
    )
    reporter.check(
        f"{pack.name}.mode_consistency",
        not bool(fleet_mode_errors.any()) and not bool(freight_mode_errors.any()),
        f"{pack.name}: vehicle, fleet, freight, and leg modes are consistent",
        details={
            "fleet_mismatches": int(fleet_mode_errors.sum()),
            "freight_mismatches": int(freight_mode_errors.sum()),
        },
    )

    range_checks = {
        "nodes.lat": _series_in_range(frames["nodes"]["lat"], -90, 90),
        "nodes.lon": _series_in_range(frames["nodes"]["lon"], -180, 180),
        "legs.distance_km": _series_in_range(frames["legs"]["distance_km"], 0, None, strict_lower=True),
        "legs.duration_hr_base": _series_in_range(frames["legs"]["duration_hr_base"], 0, None, strict_lower=True),
        "commodities.perishability_level": _series_in_range(frames["commodities"]["perishability_level"], 1, 5),
        "commodities.max_hold_hours": _series_in_range(frames["commodities"]["max_hold_hours"], 0, None, strict_lower=True),
        "commodities.loss_pct_per_hour": _series_in_range(frames["commodities"]["loss_pct_per_hour"], 0, None),
        "commodities.value_vnd_per_kg": _series_in_range(frames["commodities"]["value_vnd_per_kg"], 0, None, strict_lower=True),
        "orders.weight_kg": _series_in_range(frames["orders"]["weight_kg"], 0, None, strict_lower=True),
        "orders.priority_level": _series_in_range(frames["orders"]["priority_level"], 1, 5),
        "weather.rainfall_mm": _series_in_range(frames["weather"]["rainfall_mm"], 0, None),
        "weather.flood_risk_idx": _series_in_range(frames["weather"]["flood_risk_idx"], 0, 1),
        "weather.road_factor": _series_in_range(frames["weather"]["road_factor"], 1, None),
        "weather.water_factor": _series_in_range(frames["weather"]["water_factor"], 1, None),
        "fleet.capacity_ton": _series_in_range(frames["fleet"]["capacity_ton"], 0, None, strict_lower=True),
        "fleet.cost_fixed_vnd": _series_in_range(frames["fleet"]["cost_fixed_vnd"], 0, None),
        "fleet.cost_per_km_vnd": _series_in_range(frames["fleet"]["cost_per_km_vnd"], 0, None),
        "fleet.speed_kmh": _series_in_range(frames["fleet"]["speed_kmh"], 0, None, strict_lower=True),
        "fuel_prices.price_vnd_per_liter": _series_in_range(frames["fuel_prices"]["price_vnd_per_liter"], 0, None, strict_lower=True),
        "freight_rates.fuel_price_vnd_per_liter": _series_in_range(frames["freight_rates"]["fuel_price_vnd_per_liter"], 0, None, strict_lower=True),
        "freight_rates.fuel_cost_factor": _series_in_range(frames["freight_rates"]["fuel_cost_factor"], 0, None, strict_lower=True),
        "freight_rates.rate_vnd_per_ton_km": _series_in_range(frames["freight_rates"]["rate_vnd_per_ton_km"], 0, None, strict_lower=True),
        "freight_rates.fixed_fee_vnd": _series_in_range(frames["freight_rates"]["fixed_fee_vnd"], 0, None),
        "freight_rates.demand_idx": _series_in_range(frames["freight_rates"]["demand_idx"], 0, None, strict_lower=True),
        "weather_bulletins.max_rainfall_mm": _series_in_range(frames["weather_bulletins"]["max_rainfall_mm"], 0, None),
        "weather_bulletins.max_flood_risk_idx": _series_in_range(frames["weather_bulletins"]["max_flood_risk_idx"], 0, 1),
    }
    reporter.check(
        f"{pack.name}.ranges",
        all(range_checks.values()),
        f"{pack.name}: all numeric values satisfy contract ranges and finiteness",
        details={key: value for key, value in range_checks.items() if not value},
    )

    river_nodes = set(frames["nodes"].loc[frames["nodes"]["on_river"] == True, "node_id"])  # noqa: E712
    river_rows = frames["weather"]["node_id"].isin(river_nodes)
    reporter.check(
        f"{pack.name}.weather.river_level_required",
        not frames["weather"].loc[river_rows, "river_level_m"].isna().any(),
        f"{pack.name}/weather: river_level_m is present for every on-river node",
    )

    text_checks = {
        "weather_bulletins.headline": frames["weather_bulletins"]["headline"].map(
            lambda value: len(str(value).strip()) >= 20
        ).all(),
        "weather_bulletins.bulletin_text": frames["weather_bulletins"]["bulletin_text"].map(
            lambda value: len(str(value).strip()) >= 100
        ).all(),
        "weather_bulletins.evidence_ref": frames["weather_bulletins"]["evidence_ref"].map(
            lambda value: str(value).startswith("weather:")
        ).all(),
        "ops_notes.note_text": frames["ops_notes"]["note_text"].map(
            lambda value: len(str(value).strip()) >= 60
        ).all(),
        "ops_notes.evidence_ref": frames["ops_notes"]["evidence_ref"].map(
            lambda value: str(value).startswith(("fleet:", "orders:"))
        ).all(),
        "policy_docs.policy_text": frames["policy_docs"]["policy_text"].map(
            lambda value: len(str(value).strip()) >= 80
        ).all(),
        "policy_docs.citation_ref": frames["policy_docs"]["citation_ref"].map(
            lambda value: bool(str(value).strip())
        ).all(),
    }
    reporter.check(
        f"{pack.name}.grounding.text_quality",
        all(bool(value) for value in text_checks.values()),
        f"{pack.name}: grounding tables contain substantive text and machine-readable evidence references",
        details={key: bool(value) for key, value in text_checks.items() if not bool(value)},
    )

    fuel_link_ok = True
    fuel_link_errors: list[str] = []
    tolerance = float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6))
    pass_through = pack.config.get("freight_generation", {}).get("fuel_pass_through", {})
    base_prices = pack.config.get("fuel_generation", {}).get("base_prices_vnd_per_liter", {})
    for mode in ("road", "water"):
        fuel_type = str(pass_through.get("mode_fuel_type", {}).get(mode, ""))
        beta = float(pass_through.get("beta_by_mode", {}).get(mode, math.nan))
        minimum_factor = float(pass_through.get("minimum_factor", math.nan))
        base_price = float(base_prices.get(fuel_type, math.nan))
        quote_rows = frames["freight_rates"].loc[
            frames["freight_rates"]["mode"] == mode,
            ["ts", "fuel_type", "fuel_price_vnd_per_liter", "fuel_cost_factor"],
        ].drop_duplicates()
        fuel_rows = frames["fuel_prices"].loc[
            frames["fuel_prices"]["fuel_type"] == fuel_type,
            ["ts", "price_vnd_per_liter"],
        ].copy()
        if quote_rows.empty or fuel_rows.empty or not all(
            math.isfinite(value) for value in (beta, minimum_factor, base_price)
        ):
            fuel_link_ok = False
            fuel_link_errors.append(f"{mode}: missing configuration or rows")
            continue
        quote_rows = quote_rows.assign(_time=pd.to_datetime(quote_rows["ts"], utc=True)).sort_values("_time")
        fuel_rows = fuel_rows.assign(_time=pd.to_datetime(fuel_rows["ts"], utc=True)).sort_values("_time")
        joined = pd.merge_asof(
            quote_rows,
            fuel_rows[["_time", "price_vnd_per_liter"]],
            on="_time",
            direction="backward",
            suffixes=("_quote", "_source"),
        )
        expected_factor = np.maximum(
            minimum_factor,
            1.0 + beta * (joined["price_vnd_per_liter"].astype(float) / base_price - 1.0),
        )
        mode_ok = (
            (joined["fuel_type"] == fuel_type).all()
            and np.isclose(
                joined["fuel_price_vnd_per_liter"].astype(float),
                joined["price_vnd_per_liter"].astype(float),
                rtol=tolerance,
                atol=tolerance,
            ).all()
            and np.isclose(
                joined["fuel_cost_factor"].astype(float),
                expected_factor,
                rtol=tolerance,
                atol=tolerance,
            ).all()
        )
        if not bool(mode_ok):
            fuel_link_ok = False
            fuel_link_errors.append(f"{mode}: as-of price or factor mismatch")
    reporter.check(
        f"{pack.name}.freight.fuel_pass_through",
        fuel_link_ok,
        f"{pack.name}/freight_rates: fuel price and pass-through factor reconcile to fuel_prices and YAML beta",
        details={"errors": fuel_link_errors},
    )


def _to_utc_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _group_time_monotonic(frame: pd.DataFrame, groups: Sequence[str], ts_column: str) -> bool:
    if frame.empty:
        return False
    for _, subset in frame.groupby(list(groups), sort=False, dropna=False):
        times = _to_utc_series(subset[ts_column])
        if times.isna().any() or not times.is_monotonic_increasing:
            return False
    return True


def _validate_temporal_and_coverage(pack: Pack, reporter: Reporter) -> None:
    frames = pack.csv_typed
    if set(frames) != set(TABLE_NAMES):
        return
    dataset_cfg = pack.config.get("dataset", {})
    expected_offset = _expected_offset(pack.config)
    start = _parse_datetime(dataset_cfg.get("start"), expected_offset)
    end = _parse_datetime(dataset_cfg.get("end"), expected_offset)
    if start is None or end is None or start > end:
        reporter.check(
            f"{pack.name}.config.window",
            False,
            f"{pack.name}: resolved config start/end are valid and ordered",
        )
        return

    orders = frames["orders"]
    order_times_ok = bool(
        (
            _to_utc_series(orders["arrival_ts"])
            <= _to_utc_series(orders["ready_ts"])
        ).all()
        and (
            _to_utc_series(orders["ready_ts"])
            < _to_utc_series(orders["deadline_ts"])
        ).all()
    )
    arrivals = _to_utc_series(orders["arrival_ts"])
    order_window_ok = bool(
        (arrivals >= pd.Timestamp(start).tz_convert("UTC")).all()
        and (arrivals <= pd.Timestamp(end).tz_convert("UTC")).all()
    )
    reporter.check(
        f"{pack.name}.orders.temporal",
        order_times_ok and order_window_ok,
        f"{pack.name}/orders: arrival <= ready < deadline and arrivals stay inside the pack window",
    )

    weather = frames["weather"]
    frequency_hours = int(pack.config.get("weather_generation", {}).get("frequency_hours", 1))
    expected_hours = pd.date_range(start=start, end=end, freq=f"{frequency_hours}h", tz=start.tzinfo)
    active_nodes = set(
        frames["nodes"].loc[frames["nodes"]["active"] == True, "node_id"]  # noqa: E712
    )
    expected_ns = set(expected_hours.tz_convert("UTC").astype("int64").tolist())
    coverage_errors: dict[str, Any] = {}
    for node_id in sorted(active_nodes):
        subset = weather.loc[weather["node_id"] == node_id, "ts"]
        actual_times = _to_utc_series(subset)
        actual_ns = set(actual_times.astype("int64").tolist()) if not actual_times.isna().any() else set()
        if len(subset) != len(expected_hours) or actual_ns != expected_ns:
            coverage_errors[str(node_id)] = {
                "rows": len(subset),
                "expected_rows": len(expected_hours),
                "missing_hours": len(expected_ns - actual_ns),
                "extra_hours": len(actual_ns - expected_ns),
            }
    unknown_weather_nodes = set(weather["node_id"].dropna()) - active_nodes
    exact_weather_rows = len(weather) == len(expected_hours) * len(active_nodes)
    reporter.check(
        f"{pack.name}.weather.hourly_coverage",
        not coverage_errors and not unknown_weather_nodes and exact_weather_rows,
        f"{pack.name}/weather: every active node has exact hourly coverage for the full window",
        details={
            "hours_per_node": len(expected_hours),
            "active_nodes": len(active_nodes),
            "coverage_errors": coverage_errors,
            "unexpected_nodes": unknown_weather_nodes,
        },
    )
    reporter.check(
        f"{pack.name}.weather.monotonic",
        _group_time_monotonic(weather, ["node_id"], "ts"),
        f"{pack.name}/weather: timestamps increase within every node",
    )

    fuel = frames["fuel_prices"]
    fuel_window_ok = True
    fuel_stepwise_ok = True
    start_utc = pd.Timestamp(start).tz_convert("UTC")
    end_utc = pd.Timestamp(end).tz_convert("UTC")
    for _, subset in fuel.groupby("fuel_type", sort=False):
        times = _to_utc_series(subset["ts"])
        if times.empty or times.min() > start_utc or (times < start_utc).any() or (times > end_utc).any():
            fuel_window_ok = False
        dates_valid = all(
            adjustment is not None and timestamp is not None and adjustment <= timestamp.date()
            for adjustment, timestamp in zip(subset["adjustment_date"], subset["ts"])
        )
        stable_by_adjustment = (
            subset.groupby("adjustment_date", dropna=False)["price_vnd_per_liter"].nunique(dropna=False) <= 1
        ).all()
        fuel_stepwise_ok = fuel_stepwise_ok and dates_valid and bool(stable_by_adjustment)
    reporter.check(
        f"{pack.name}.fuel.forward_fill",
        fuel_window_ok and _group_time_monotonic(fuel, ["fuel_type"], "ts"),
        f"{pack.name}/fuel_prices: each fuel series starts at the window boundary and can be forward-filled",
    )
    reporter.check(
        f"{pack.name}.fuel.stepwise",
        fuel_stepwise_ok,
        f"{pack.name}/fuel_prices: prices are stable within each adjustment period",
    )

    freight = frames["freight_rates"]
    frequency = int(pack.config.get("freight_generation", {}).get("frequency_hours", 6))
    max_gap = pd.Timedelta(hours=frequency)
    freight_coverage_ok = True
    for _, subset in freight.groupby(["leg_id", "vehicle_type", "rate_type"], sort=False):
        times = _to_utc_series(subset["ts"])
        if times.empty:
            freight_coverage_ok = False
            continue
        sorted_times = times.sort_values()
        gaps = sorted_times.diff().dropna()
        if (
            sorted_times.iloc[0] > start_utc
            or sorted_times.iloc[0] < start_utc
            or sorted_times.iloc[-1] > end_utc
            or end_utc - sorted_times.iloc[-1] >= max_gap
            or (not gaps.empty and gaps.max() > max_gap)
        ):
            freight_coverage_ok = False
    reporter.check(
        f"{pack.name}.freight.asof_coverage",
        freight_coverage_ok
        and _group_time_monotonic(freight, ["leg_id", "vehicle_type", "rate_type"], "ts"),
        f"{pack.name}/freight_rates: every series supports nearest-previous joins over the full window",
    )

    reporter.check(
        f"{pack.name}.fleet.available_from",
        not _to_utc_series(frames["fleet"]["available_from_ts"]).isna().any(),
        f"{pack.name}/fleet: every available_from_ts is a valid timezone-aware timestamp",
    )

    bulletins = frames["weather_bulletins"].copy()
    bulletin_temporal_ok = bool(
        (_to_utc_series(bulletins["issued_at"]) <= _to_utc_series(bulletins["valid_from"])).all()
        and (_to_utc_series(bulletins["valid_from"]) <= _to_utc_series(bulletins["valid_to"])).all()
    )
    weather_for_daily = weather.copy()
    weather_for_daily["_date"] = weather_for_daily["ts"].map(
        lambda value: value.date() if value is not None else None
    )
    bulletin_dates = bulletins["valid_from"].map(
        lambda value: value.date() if value is not None else None
    )
    bulletins["_date"] = bulletin_dates
    daily_weather = (
        weather_for_daily.groupby(["_date", "node_id"], as_index=False)
        .agg(
            expected_rain=("rainfall_mm", "max"),
            expected_risk=("flood_risk_idx", "max"),
        )
    )
    bulletin_join = bulletins.merge(
        daily_weather,
        on=["_date", "node_id"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    bulletin_values_ok = bool(
        (bulletin_join["_merge"] == "both").all()
        and np.isclose(
            bulletin_join["max_rainfall_mm"].astype(float),
            bulletin_join["expected_rain"].astype(float),
            rtol=float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6)),
            atol=float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6)),
        ).all()
        and np.isclose(
            bulletin_join["max_flood_risk_idx"].astype(float),
            bulletin_join["expected_risk"].astype(float),
            rtol=float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6)),
            atol=float(pack.config.get("validation", {}).get("numeric_tolerance", 1e-6)),
        ).all()
    )
    reporter.check(
        f"{pack.name}.grounding.weather_bulletins",
        bulletin_temporal_ok and bulletin_values_ok,
        f"{pack.name}/weather_bulletins: one grounded daily bulletin per node reconciles to weather maxima",
        details={"bulletins": len(bulletins), "daily_weather_groups": len(daily_weather)},
    )

    notes = frames["ops_notes"]
    note_temporal_ok = bool(
        (_to_utc_series(notes["created_at"]) <= _to_utc_series(notes["valid_until"])).all()
    )
    vehicle_notes = notes.loc[notes["note_type"] == "vehicle_status"]
    intake_notes = notes.loc[notes["note_type"] == "daily_intake"]
    expected_days = len(pd.date_range(pd.Timestamp(start).floor("D"), pd.Timestamp(end).floor("D"), freq="D"))
    expected_intake = expected_days * len(pack.config.get("order_generation", {}).get("hubs", {}))
    notes_ok = (
        note_temporal_ok
        and len(vehicle_notes) == len(frames["fleet"])
        and set(vehicle_notes["vehicle_id"].dropna()) == set(frames["fleet"]["vehicle_id"])
        and len(intake_notes) == expected_intake
    )
    reporter.check(
        f"{pack.name}.grounding.ops_notes",
        notes_ok,
        f"{pack.name}/ops_notes: vehicle and daily-intake notes have valid coverage without output-label leakage",
        details={
            "vehicle_notes": len(vehicle_notes),
            "expected_vehicle_notes": len(frames["fleet"]),
            "intake_notes": len(intake_notes),
            "expected_intake_notes": expected_intake,
        },
    )
    reporter.check(
        f"{pack.name}.grounding.policy_docs",
        len(frames["policy_docs"]) >= 10,
        f"{pack.name}/policy_docs: at least ten citable SOP/policy records are available",
        details={"rows": len(frames["policy_docs"])},
    )

    validation_cfg = pack.config.get("validation", {})
    required_hubs = set(validation_cfg.get("required_hubs", []))
    required_commodities = set(validation_cfg.get("required_commodities", []))
    node_ids = set(frames["nodes"]["node_id"])
    commodity_ids = set(frames["commodities"]["commodity_id"])
    reporter.check(
        f"{pack.name}.coverage.required_reference",
        required_hubs.issubset(node_ids) and required_commodities.issubset(commodity_ids),
        f"{pack.name}: all required hubs and commodities are present",
        details={
            "missing_hubs": required_hubs - node_ids,
            "missing_commodities": required_commodities - commodity_ids,
        },
    )

    modes_ok = all(
        {"road", "water"}.issubset(set(frames[table]["mode"]))
        for table in ("legs", "fleet", "freight_rates")
    )
    statuses = set(frames["fleet"]["status"])
    reporter.check(
        f"{pack.name}.coverage.modes_and_fleet_states",
        modes_ok and "available" in statuses and bool(statuses - {"available"}),
        f"{pack.name}: road/water data and both available/unavailable fleet states exist",
        details={"fleet_statuses": statuses},
    )

    required_vehicle_types = set(VEHICLE_MODES)
    reporter.check(
        f"{pack.name}.coverage.vehicle_types",
        required_vehicle_types.issubset(set(frames["fleet"]["vehicle_type"])),
        f"{pack.name}: all six required fleet vehicle types are present",
        details={"missing": required_vehicle_types - set(frames["fleet"]["vehicle_type"])},
    )

    legs = frames["legs"]
    leg_coverage_errors: list[str] = []
    for hub in sorted(required_hubs):
        direct_road = (
            (legs["from_node_id"] == hub)
            & (legs["to_node_id"] == "HCM_MARKET")
            & (legs["mode"] == "road")
        ).any()
        ct_road = (
            (legs["from_node_id"] == hub)
            & (legs["to_node_id"] == "CT_HUB")
            & (legs["mode"] == "road")
        ).any()
        node_is_river = bool(
            frames["nodes"].loc[frames["nodes"]["node_id"] == hub, "on_river"].fillna(False).any()
        )
        ct_water = (
            (legs["from_node_id"] == hub)
            & (legs["to_node_id"] == "CT_HUB")
            & (legs["mode"] == "water")
        ).any()
        if not direct_road or not ct_road or (node_is_river and not ct_water):
            leg_coverage_errors.append(hub)
    ct_outbound_modes = set(
        legs.loc[
            (legs["from_node_id"] == "CT_HUB") & (legs["to_node_id"] == "HCM_MARKET"),
            "mode",
        ]
    )
    reporter.check(
        f"{pack.name}.coverage.route_legs",
        not leg_coverage_errors and {"road", "water"}.issubset(ct_outbound_modes),
        f"{pack.name}/legs: required direct, consolidation, water, and CT outbound coverage exists",
        details={"hub_errors": leg_coverage_errors, "ct_outbound_modes": ct_outbound_modes},
    )

    fleet_hub_errors: list[str] = []
    for hub in sorted(required_hubs):
        at_hub = frames["fleet"]["current_node_id"] == hub
        if not (at_hub & (frames["fleet"]["mode"] == "road")).any():
            fleet_hub_errors.append(f"{hub}:road")
        node_is_river = bool(
            frames["nodes"].loc[frames["nodes"]["node_id"] == hub, "on_river"].fillna(False).any()
        )
        if node_is_river and not (at_hub & (frames["fleet"]["mode"] == "water")).any():
            fleet_hub_errors.append(f"{hub}:water")
    reporter.check(
        f"{pack.name}.coverage.fleet_by_hub",
        not fleet_hub_errors,
        f"{pack.name}/fleet: required hubs have appropriate road and water assets",
        details={"missing": fleet_hub_errors},
    )

    if pack.name == "annual":
        target = pack.config.get("order_generation", {}).get("target_annual_rows", {})
        minimum = int(target.get("min", 6000))
        maximum = int(target.get("max", 12000))
        reporter.check(
            "annual.orders.row_count",
            minimum <= len(orders) <= maximum,
            f"annual/orders: row count is within configured target [{minimum}, {maximum}]",
            details={"actual": len(orders)},
        )
        months = {timestamp.month for timestamp in orders["arrival_ts"] if timestamp is not None}
        reporter.check(
            "annual.orders.month_coverage",
            months == set(range(1, 13)),
            "annual/orders: orders appear in all 12 calendar months",
            details={"months": months},
        )
        mix_errors: list[str] = []
        configured_hubs = pack.config.get("order_generation", {}).get("hubs", {})
        for hub, hub_cfg in configured_hubs.items():
            for commodity in hub_cfg.get("commodity_mix", {}):
                if not ((orders["hub_id"] == hub) & (orders["commodity_id"] == commodity)).any():
                    mix_errors.append(f"{hub}/{commodity}")
        reporter.check(
            "annual.orders.configured_mix_coverage",
            not mix_errors,
            "annual/orders: every configured hub/commodity combination appears",
            details={"missing": mix_errors},
        )

        order_frame = orders.copy()
        order_frame["_arrival"] = pd.to_datetime(order_frame["arrival_ts"])
        order_frame["_date"] = order_frame["_arrival"].dt.floor("D")
        order_frame["_hour"] = order_frame["_arrival"].dt.floor("h")
        hubs = sorted(pack.config.get("order_generation", {}).get("hubs", {}))
        days = pd.date_range(
            pd.Timestamp(start).floor("D"),
            pd.Timestamp(end).floor("D"),
            freq="D",
        )
        daily_grid = pd.MultiIndex.from_product([days, hubs], names=["_date", "hub_id"])
        daily = (
            order_frame.groupby(["_date", "hub_id"]).size()
            .reindex(daily_grid, fill_value=0)
            .rename("orders")
            .reset_index()
        )
        daily["month"] = daily["_date"].dt.month
        daily["dow"] = daily["_date"].dt.dayofweek
        prediction = daily.groupby(["hub_id", "month", "dow"])["orders"].transform("mean")
        residual = float(np.square(daily["orders"] - prediction).sum())
        total = float(np.square(daily["orders"] - daily["orders"].mean()).sum())
        calendar_r2 = 1.0 - residual / total if total > 0 else math.nan
        variance_mean = daily.groupby("hub_id")["orders"].agg(["mean", "var"])
        variance_mean_ratio = float((variance_mean["var"] / variance_mean["mean"]).mean())
        monthly_tonnage = order_frame.groupby(order_frame["_arrival"].dt.month)["weight_kg"].sum()
        peak_trough = float(monthly_tonnage.max() / monthly_tonnage.min())
        hours = pd.date_range(pd.Timestamp(start).floor("h"), pd.Timestamp(end).floor("h"), freq="h")
        hourly_grid = pd.MultiIndex.from_product([hours, hubs], names=["_hour", "hub_id"])
        hourly = order_frame.groupby(["_hour", "hub_id"]).size().reindex(hourly_grid, fill_value=0)
        zero_share = float((hourly == 0).mean())
        guardrails = validation_cfg.get("demand_signal_guardrails", {})

        def inside(metric: float, rule: Mapping[str, Any]) -> bool:
            return (
                math.isfinite(metric)
                and metric >= float(rule.get("min", -math.inf))
                and metric <= float(rule.get("max", math.inf))
            )

        signal_ok = (
            inside(calendar_r2, guardrails.get("calendar_oracle_r2", {}))
            and inside(peak_trough, guardrails.get("monthly_tonnage_peak_trough", {}))
            and inside(variance_mean_ratio, guardrails.get("daily_variance_mean_ratio", {}))
            and zero_share <= float(guardrails.get("hourly_zero_share_max", 1.0))
            and pack.config.get("order_generation", {}).get("forecast_grain") == "day"
        )
        reporter.check(
            "annual.orders.learnability_guardrails",
            signal_ok,
            "annual/orders: daily demand signal stays inside broad anti-underfit/anti-overfit guardrails",
            details={
                "calendar_oracle_r2": calendar_r2,
                "monthly_tonnage_peak_trough": peak_trough,
                "daily_variance_mean_ratio": variance_mean_ratio,
                "hourly_zero_share": zero_share,
                "forecast_grain": pack.config.get("order_generation", {}).get("forecast_grain"),
                "guardrails": guardrails,
            },
        )


def _evaluation_order_checksum(order: pd.Series) -> str:
    payload = json.dumps(order.to_dict(), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_evaluation_set(packs: Mapping[str, Pack], reporter: Reporter) -> None:
    eval_dir = PROJECT_ROOT / "eval"
    csv_path = eval_dir / "reference_routes.csv"
    json_path = eval_dir / "reference_routes.json"
    metadata_path = eval_dir / "metadata.json"
    files_ok = csv_path.is_file() and json_path.is_file() and metadata_path.is_file()
    if not reporter.check(
        "evaluation.files",
        files_ok,
        "Held-out evaluation CSV, JSON, and metadata files exist under eval/",
    ):
        return
    try:
        frame = pd.read_csv(csv_path, keep_default_na=False, encoding="utf-8")
        json_records = json.loads(json_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        reporter.check(
            "evaluation.parse",
            False,
            f"Evaluation artifacts parse as UTF-8 CSV/JSON: {exc}",
        )
        return

    config = load_config(PROJECT_ROOT / "config" / "base.yaml")
    target_rows = int(config.get("evaluation", {}).get("target_rows", 50))
    schema_ok = tuple(frame.columns) == EVAL_COLUMNS
    json_schema_ok = (
        isinstance(json_records, list)
        and len(json_records) == len(frame)
        and all(tuple(record.keys()) == EVAL_COLUMNS for record in json_records)
    )
    reporter.check(
        "evaluation.schema_and_size",
        schema_ok
        and json_schema_ok
        and len(frame) == target_rows
        and frame["eval_id"].is_unique
        and not frame.duplicated(["pack", "order_id"]).any(),
        "Evaluation set has the exact frozen schema, 50 unique held-out cases, and CSV/JSON parity",
        details={"rows": len(frame), "target_rows": target_rows},
    )

    allowed_routes = {"A_DIRECT_ROAD", "B_ROAD_VIA_CT", "C_WATER_VIA_CT", "INFEASIBLE"}
    reference_ok = set(frame["reference_route"]).issubset(allowed_routes)
    source_errors: list[str] = []
    for pack_name, subset in frame.groupby("pack", sort=False):
        pack = packs.get(str(pack_name))
        if pack is None or pack_name == "annual":
            source_errors.append(f"unknown pack {pack_name}")
            continue
        source_orders = pd.read_csv(pack.path / "csv" / "orders.csv").set_index(
            "order_id", drop=False
        )
        for row in subset.itertuples(index=False):
            if row.order_id not in source_orders.index:
                source_errors.append(f"{pack_name}/{row.order_id}: missing order")
                continue
            checksum = _evaluation_order_checksum(source_orders.loc[row.order_id])
            if checksum != row.source_order_sha256:
                source_errors.append(f"{pack_name}/{row.order_id}: checksum mismatch")
            feasible = {part for part in str(row.feasible_routes).split("|") if part}
            if row.reference_route == "INFEASIBLE":
                if feasible:
                    source_errors.append(f"{pack_name}/{row.order_id}: infeasible but feasible list non-empty")
            elif row.reference_route not in feasible:
                source_errors.append(f"{pack_name}/{row.order_id}: reference route not feasible")
    reporter.check(
        "evaluation.source_integrity",
        reference_ok and not source_errors,
        "Evaluation labels reference real scenario orders, preserve source checksums, and do not leak into inputs",
        details={"errors": source_errors[:20]},
    )

    declared_checksums = metadata.get("checksums", {}) if isinstance(metadata, Mapping) else {}
    metadata_ok = (
        str(metadata.get("dataset_version")) == str(config["dataset"]["version"])
        and int(metadata.get("actual_rows", -1)) == len(frame)
        and declared_checksums.get(csv_path.name) == sha256_file(csv_path)
        and declared_checksums.get(json_path.name) == sha256_file(json_path)
    )
    reporter.check(
        "evaluation.metadata",
        metadata_ok,
        "Evaluation metadata version, row count, and checksums match the held-out files",
    )


def _validate_scenario_signals(packs: Mapping[str, Pack], reporter: Reporter) -> None:
    required = ("S1_normal", "S2_flood", "S3_price_shock")
    if any(name not in packs or set(packs[name].csv_typed) != set(TABLE_NAMES) for name in required):
        reporter.check(
            "scenarios.precondition",
            False,
            "Scenario signal checks require all three complete scenario packs",
        )
        return
    s1, s2, s3 = (packs[name] for name in required)

    schemas_equal = all(
        list(s1.csv_raw[table].columns) == list(s2.csv_raw[table].columns) == list(s3.csv_raw[table].columns)
        for table in TABLE_NAMES
    )
    reporter.check(
        "scenarios.same_schema",
        schemas_equal,
        f"S1, S2, and S3 use identical schemas for all {len(TABLE_NAMES)} canonical tables",
    )

    target_nodes = set(s2.config.get("scenario", {}).get("weather", {}).get("target_node_multipliers", {}))
    for event in s2.config.get("scenario", {}).get("weather", {}).get("extreme_events", []):
        target_nodes.update(event.get("affected_nodes", []))
    if not target_nodes:
        target_nodes = set(s2.config.get("validation", {}).get("required_hubs", []))
    s1_weather = s1.csv_typed["weather"]
    s2_weather = s2.csv_typed["weather"]
    weather_metrics: dict[str, dict[str, float]] = {}
    weather_signal_ok = bool(target_nodes)
    for metric in ("rainfall_mm", "flood_risk_idx", "road_factor"):
        normal_mean = float(s1_weather.loc[s1_weather["node_id"].isin(target_nodes), metric].mean())
        flood_mean = float(s2_weather.loc[s2_weather["node_id"].isin(target_nodes), metric].mean())
        weather_metrics[metric] = {"S1": normal_mean, "S2": flood_mean}
        weather_signal_ok = weather_signal_ok and flood_mean > normal_mean
    reporter.check(
        "scenarios.S2_weather_signal",
        weather_signal_ok,
        "S2 target nodes have higher mean rainfall, flood risk, and road factor than S1",
        details={"target_nodes": target_nodes, "means": weather_metrics},
    )

    s2_bulletins = s2.csv_typed["weather_bulletins"]
    closed_water = s2_bulletins.loc[
        s2_bulletins["node_id"].isin(target_nodes)
        & (s2_bulletins["water_navigation_status"] == "closed")
    ]
    reporter.check(
        "scenarios.S2_navigation_closure_signal",
        len(closed_water) > 0,
        "S2 produces at least one explicit target-node water closure instead of only a finite penalty",
        details={"closed_bulletins": len(closed_water)},
    )

    s1_diesel = s1.csv_typed["fuel_prices"].loc[
        s1.csv_typed["fuel_prices"]["fuel_type"] == "diesel_005s", ["ts", "price_vnd_per_liter"]
    ].sort_values("ts")
    s3_diesel = s3.csv_typed["fuel_prices"].loc[
        s3.csv_typed["fuel_prices"]["fuel_type"] == "diesel_005s", ["ts", "price_vnd_per_liter"]
    ].sort_values("ts")
    diesel_path = s3.config.get("scenario", {}).get("fuel_price_paths", {}).get("diesel_005s", [])
    s3_start = pd.Timestamp(s3.config.get("dataset", {}).get("start"))
    expected_times = [
        s3_start + pd.Timedelta(hours=int(item["offset_hours"]))
        for item in diesel_path
    ]
    expected_ratios = np.asarray([float(item["multiplier"]) for item in diesel_path], dtype=float)
    actual_times = pd.DatetimeIndex(pd.to_datetime(s3_diesel["ts"])).tolist()
    s1_base_price = float(s1_diesel.iloc[0]["price_vnd_per_liter"])
    actual_ratios = s3_diesel["price_vnd_per_liter"].astype(float).to_numpy() / s1_base_price
    tolerance = float(s3.config.get("validation", {}).get("numeric_tolerance", 1e-6))
    diesel_ok = (
        len(expected_times) >= 3
        and len(s3_diesel) == len(expected_times)
        and actual_times == expected_times
        and bool(np.isclose(actual_ratios, expected_ratios, rtol=tolerance, atol=tolerance).all())
        and bool(np.diff(actual_ratios).min() > 0)
    )
    reporter.check(
        "scenarios.S3_diesel_signal",
        diesel_ok,
        "S3 diesel follows the configured multi-step shock path and reaches the 1.18x terminal level",
        details={
            "expected_ratios": expected_ratios.tolist(),
            "actual_ratios": actual_ratios.tolist(),
            "expected_times": [value.isoformat() for value in expected_times],
        },
    )

    s3_road_fuel_factor = (
        s3.csv_typed["freight_rates"]
        .loc[s3.csv_typed["freight_rates"]["mode"] == "road"]
        .groupby("ts", sort=True)["fuel_cost_factor"]
        .mean()
    )
    reporter.check(
        "scenarios.S3_fuel_reaches_freight",
        len(s3_road_fuel_factor) > 1
        and float(s3_road_fuel_factor.iloc[-1]) > float(s3_road_fuel_factor.iloc[0]),
        "S3 road freight exposes an increasing fuel_cost_factor tied to the staged diesel shock",
        details={
            "first_factor": float(s3_road_fuel_factor.iloc[0]) if len(s3_road_fuel_factor) else None,
            "last_factor": float(s3_road_fuel_factor.iloc[-1]) if len(s3_road_fuel_factor) else None,
        },
    )

    def road_available_share(pack: Pack) -> float:
        road = pack.csv_typed["fleet"].loc[pack.csv_typed["fleet"]["mode"] == "road"]
        return float((road["status"] == "available").mean()) if len(road) else math.nan

    def road_demand_mean(pack: Pack) -> float:
        road = pack.csv_typed["freight_rates"].loc[
            pack.csv_typed["freight_rates"]["mode"] == "road", "demand_idx"
        ]
        return float(road.mean()) if len(road) else math.nan

    available_s1 = road_available_share(s1)
    available_s3 = road_available_share(s3)
    demand_s1 = road_demand_mean(s1)
    demand_s3 = road_demand_mean(s3)
    fleet_or_demand_ok = (
        math.isfinite(available_s1)
        and math.isfinite(available_s3)
        and math.isfinite(demand_s1)
        and math.isfinite(demand_s3)
        and (available_s3 < available_s1 or demand_s3 > demand_s1)
    )
    reporter.check(
        "scenarios.S3_fleet_or_demand_signal",
        fleet_or_demand_ok,
        "S3 has lower road availability or higher road demand than S1",
        details={
            "road_available_share": {"S1": available_s1, "S3": available_s3},
            "road_demand_mean": {"S1": demand_s1, "S3": demand_s3},
        },
    )

    scenario_hashes = {name: pack_digest(packs[name].data_checksums) for name in required}
    reporter.check(
        "scenarios.pack_hashes_differ",
        len(set(scenario_hashes.values())) == len(required),
        "S1, S2, and S3 canonical data packs have pairwise-distinct aggregate hashes",
        details=scenario_hashes,
    )


def _locate_generated_pack(temp_root: Path, output_subdir: str, pack_name: str) -> Path | None:
    candidates = [temp_root / output_subdir, temp_root / pack_name, temp_root]
    for candidate in candidates:
        if all((candidate / "csv" / f"{table}.csv").is_file() for table in TABLE_NAMES) and all(
            (candidate / "json" / f"{table}.json").is_file() for table in TABLE_NAMES
        ):
            return candidate
    matches: list[Path] = []
    for metadata_path in temp_root.rglob("metadata.json"):
        candidate = metadata_path.parent
        if all((candidate / "csv" / f"{table}.csv").is_file() for table in TABLE_NAMES) and all(
            (candidate / "json" / f"{table}.json").is_file() for table in TABLE_NAMES
        ):
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def _validate_reproducibility(packs: Sequence[Pack], reporter: Reporter) -> None:
    generator = PROJECT_ROOT / "src" / "generate_data.py"
    if not reporter.check(
        "reproducibility.generator_exists",
        generator.is_file(),
        "Generator CLI exists for reproducibility checks",
    ):
        return

    for pack in packs:
        seed = int(pack.config.get("dataset", {}).get("seed", 20260717))
        output_subdir = str(pack.config.get("dataset", {}).get("output_subdir", pack.name))
        with tempfile.TemporaryDirectory(prefix=f"vaic_repro_{pack.name}_") as temp_name:
            temp_root = Path(temp_name)
            command = [
                sys.executable,
                str(generator),
                "--config",
                str(pack.config_path),
                "--seed",
                str(seed),
                "--format",
                "both",
                "--output-dir",
                str(temp_root),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=PROJECT_ROOT,
                    text=True,
                    capture_output=True,
                    timeout=600,
                    check=False,
                )
            except Exception as exc:
                reporter.check(
                    f"{pack.name}.reproducibility.invoke",
                    False,
                    f"{pack.name}: generator could not be invoked for reproducibility: {exc}",
                )
                continue
            if completed.returncode != 0:
                reporter.check(
                    f"{pack.name}.reproducibility.invoke",
                    False,
                    f"{pack.name}: generator reproducibility run exited {completed.returncode}",
                    details={
                        "command": command,
                        "stdout_tail": completed.stdout[-4000:],
                        "stderr_tail": completed.stderr[-4000:],
                    },
                )
                continue

            generated_pack = _locate_generated_pack(temp_root, output_subdir, pack.name)
            if generated_pack is None:
                reporter.check(
                    f"{pack.name}.reproducibility.output",
                    False,
                    f"{pack.name}: could not locate a complete reproduced pack under the temporary output",
                    details={"temporary_root": temp_root},
                )
                continue

            differences: dict[str, dict[str, str | None]] = {}
            for table in TABLE_NAMES:
                for directory, extension in (("csv", "csv"), ("json", "json")):
                    relative = f"{directory}/{table}.{extension}"
                    canonical_path = pack.path / relative
                    reproduced_path = generated_pack / relative
                    canonical_hash = sha256_file(canonical_path) if canonical_path.is_file() else None
                    reproduced_hash = sha256_file(reproduced_path) if reproduced_path.is_file() else None
                    if canonical_hash != reproduced_hash:
                        differences[relative] = {
                            "canonical": canonical_hash,
                            "reproduced": reproduced_hash,
                        }
            reporter.check(
                f"{pack.name}.reproducibility.checksums",
                not differences,
                f"{pack.name}: regenerated canonical CSV/JSON checksums exactly match the checked-in pack",
                details={"differences": differences},
            )


def _pack_specs(root: Path) -> list[tuple[str, Path, Path]]:
    config_paths = [
        PROJECT_ROOT / "config" / "base.yaml",
        PROJECT_ROOT / "config" / "scenarios" / "S1_normal.yaml",
        PROJECT_ROOT / "config" / "scenarios" / "S2_flood.yaml",
        PROJECT_ROOT / "config" / "scenarios" / "S3_price_shock.yaml",
    ]
    specs: list[tuple[str, Path, Path]] = []
    for config_path in config_paths:
        config = load_config(config_path)
        name = str(config.get("dataset", {}).get("pack", config_path.stem))
        output_subdir = Path(str(config.get("dataset", {}).get("output_subdir", name)))
        specs.append((name, root / output_subdir, config_path))
    return specs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate VAIC v3 generated data packs")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/generated"),
        help="Generated data root (default: data/generated)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/validation_report.json"),
        help="JSON report path (default: reports/validation_report.json)",
    )
    parser.add_argument(
        "--skip-reproducibility",
        action="store_true",
        help="Skip generator reruns; all other hard checks still run",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    root = args.root if args.root.is_absolute() else (PROJECT_ROOT / args.root)
    report_path = args.report if args.report.is_absolute() else (PROJECT_ROOT / args.report)

    version = "3.0"
    seed = 20260717
    try:
        base_config = load_config(PROJECT_ROOT / "config" / "base.yaml")
        version = str(base_config.get("dataset", {}).get("version", version))
        seed = int(base_config.get("dataset", {}).get("seed", seed))
    except Exception:
        pass
    reporter = Reporter(version, seed)
    reporter.payload["root"] = str(root)
    reporter.payload["reproducibility_skipped"] = bool(args.skip_reproducibility)

    try:
        reporter.check("root.exists", root.is_dir(), f"Generated data root exists: {root}")
        specs = _pack_specs(root)
        names = [name for name, _, _ in specs]
        reporter.check(
            "packs.expected_set",
            names == ["annual", "S1_normal", "S2_flood", "S3_price_shock"],
            "Resolved configs define annual plus the three required scenarios",
            details={"resolved": names},
        )

        packs: list[Pack] = []
        for name, path, config_path in specs:
            config = load_config(config_path)
            pack = Pack(name=name, path=path, config_path=config_path, config=config)
            packs.append(pack)
            reporter.check(
                f"{name}.directory",
                path.is_dir(),
                f"Pack directory exists: {path}",
            )
            _validate_pack_files(pack, reporter)
            _validate_keys_and_domains(pack, reporter)
            _validate_temporal_and_coverage(pack, reporter)
            compat_names = _validate_compatibility_exports(pack, reporter)
            compat_dir = str(config.get("compatibility_exports", {}).get("directory_name", "compat"))
            for filename in compat_names:
                compat_path = pack.path / compat_dir / filename
                if compat_path.is_file():
                    relative = compat_path.relative_to(pack.path).as_posix()
                    checksum = sha256_file(compat_path)
                    pack.data_checksums[relative] = checksum
                    reporter.payload["file_checksums"].setdefault(name, {})[relative] = checksum
            expected_files = _actual_data_files(pack.path, compat_names)
            _validate_metadata(pack, reporter, expected_files)

        pack_map = {pack.name: pack for pack in packs}
        _validate_scenario_signals(pack_map, reporter)
        _validate_evaluation_set(pack_map, reporter)

        annual = pack_map.get("annual")
        if annual and "nodes" in annual.csv_typed and "legs" in annual.csv_typed:
            assumptions = 0
            for table in ("nodes", "legs", "commodities", "policy_docs"):
                if table in annual.csv_typed and "source_type" in annual.csv_typed[table]:
                    assumptions += int((annual.csv_typed[table]["source_type"] == "assumption").sum())
            if assumptions:
                reporter.warning(
                    f"Reference data contains {assumptions} simulation assumption row(s); consult ANCHORS.md before external use."
                )

        if args.skip_reproducibility:
            reporter.warning("Reproducibility checks were explicitly skipped by --skip-reproducibility.")
        else:
            _validate_reproducibility(packs, reporter)

    except Exception as exc:  # Always produce a usable report, even on validator bugs.
        reporter.check(
            "validator.unhandled_exception",
            False,
            f"Validator encountered an unexpected error: {exc}",
            details={"traceback": traceback.format_exc()},
        )
    finally:
        try:
            reporter.write(report_path)
        except Exception as exc:
            print(f"ERROR: could not write validation report {report_path}: {exc}", file=sys.stderr)
            return 2

    status = reporter.payload["status"]
    passed = reporter.payload["checks_passed"]
    failed = reporter.payload["checks_failed"]
    print(f"Validation {status}: {passed} passed, {failed} failed. Report: {report_path}")
    return 1 if reporter.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
