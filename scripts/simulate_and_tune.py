"""Simulation-based tuning cho Priority Score weights (alpha/beta/gamma/threshold).

Chạy:
    cd VAIC-26-VinPaann
    python -m ai2_dispatch.scripts.simulate_and_tune
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ai1_route_optimizer.candidates import build_candidates
from ai1_route_optimizer.data_loader import DEFAULT_DATA_DIR as AI1_DATA_DIR
from ai1_route_optimizer.data_loader import load_data as load_ai1_data
from ai1_route_optimizer.data_loader import parse_ts
from ai1_route_optimizer.feasibility import leg_weather_factor
from ai1_route_optimizer.optimizer import optimize_route

from ai2_dispatch.app.data_loader import DEFAULT_DATA_DIR as AI2_DATA_DIR
from ai2_dispatch.app.decision_engine import DecisionConfig, evaluate
from ai2_dispatch.app.enums import AI1_ROUTE_TO_AI2_ROUTE, Decision, Mode, ROUTES_REQUIRING_AI2, VehicleStatus
from ai2_dispatch.app.state_store import Shipment, StateStore

# -- proxy objective weights (giả định chủ quan, xem docstring) --------------
WAIT_COST_PER_TON_HOUR = 1.0
UNDERFILL_COST_PER_TON = 1.0
SAFE_VIOLATION_PENALTY = 20.0
UNRESOLVED_PENALTY_PER_TON_HOUR = 3.0
TICK_HOURS = 3.0
RESOLUTION_BUFFER_HOURS = 48.0


@dataclass(frozen=True)
class SimShipment:
    shipment_id: str
    hub_id: str
    commodity_id: str
    weight_kg: float
    selected_route: str
    outbound_mode: Mode
    created_at: datetime
    eta_can_tho: datetime


def load_ct_bound_shipments(
    month_prefixes: tuple[str, ...] = ("2026-01", "2026-05", "2026-09"),
    ai1_data_dir=AI1_DATA_DIR,
) -> list[SimShipment]:

    store = load_ai1_data(ai1_data_dir)
    orders = [
        o
        for o in store.orders.values()
        if o["ready_ts"].startswith(month_prefixes) and o.get("status") != "cancelled"
    ]
    orders.sort(key=lambda o: o["ready_ts"])

    shipments: list[SimShipment] = []
    for order in orders:
        decision_ts = parse_ts(order["ready_ts"])
        try:
            result = optimize_route(
                {
                    "order_id": order["order_id"],
                    "hub_id": order["hub_id"],
                    "commodity_id": order["commodity_id"],
                    "khoi_luong_kg": float(order["weight_kg"]),
                    "timestamp": order["ready_ts"],
                },
                data_dir=ai1_data_dir,
            )
        except ValueError:
            continue

        route_code = result.get("recommended_route")
        if route_code is None or route_code not in AI1_ROUTE_TO_AI2_ROUTE:
            continue
        route_enum, _inbound_mode, outbound_mode = AI1_ROUTE_TO_AI2_ROUTE[route_code]
        if route_enum not in ROUTES_REQUIRING_AI2:
            continue  # direct_hcm_road, không thuộc AI2

        candidate = next(c for c in build_candidates(order["hub_id"], store.legs) if c.route_code == route_code)
        inbound_leg = store.legs[candidate.leg_ids[0]]
        factor, _ts, _reason = leg_weather_factor(store, inbound_leg, decision_ts)
        inbound_hours = inbound_leg["duration_hr_base"] * factor
        eta_can_tho = decision_ts + timedelta(hours=inbound_hours)

        shipments.append(
            SimShipment(
                shipment_id=order["order_id"],
                hub_id=order["hub_id"],
                commodity_id=order["commodity_id"],
                weight_kg=float(order["weight_kg"]),
                selected_route=route_enum,
                outbound_mode=outbound_mode,
                created_at=decision_ts,
                eta_can_tho=eta_can_tho,
            )
        )
    return shipments


@dataclass
class SimMetrics:
    total_loss: float
    dispatch_count: int
    safe_violation_count: int
    unresolved_count: int
    avg_fill_ratio: float
    avg_wait_hours: float


def _round_trip_hours(ai1_data_dir=AI1_DATA_DIR) -> dict[Mode, float]:
    """Fleet tại CT_HUB hữu hạn (13 xe road + 14 phương tiện water — xem CHANGELOG). Nếu không
    mô phỏng xe quay lại sau khi dispatch, fleet cạn kiệt sau vài lượt và gần như toàn bộ
    shipment còn lại bị coi là "unresolved" — sai lệch nghiêm trọng so với vận hành thật. Ước
    lượng round-trip = 2 x leg CT_HUB->HCM_MARKET (đi + về) + 2h đệm bốc dỡ, lấy từ
    `duration_hr_base` thật trong `legs.csv`."""

    store = load_ai1_data(ai1_data_dir)
    hours: dict[Mode, float] = {}
    for leg in store.legs.values():
        if leg["from_node_id"] == "CT_HUB" and leg["to_node_id"] == "HCM_MARKET":
            hours[Mode(leg["mode"])] = 2 * float(leg["duration_hr_base"]) + 2.0
    return hours


def _run_episode(
    shipments: list[SimShipment], config: DecisionConfig, ai2_data_dir=AI2_DATA_DIR
) -> SimMetrics:
    """Chạy 1 episode liên tục (thường là 1 tháng). Xem `run_simulation()`
    để chạy nhiều tháng độc lập rồi cộng dồn kết quả."""

    store = StateStore(data_dir=ai2_data_dir, persist_path=None)
    round_trip_hours = _round_trip_hours()
    pending_returns: list[tuple[datetime, str]] = []

    actions_by_ts: dict[datetime, list[tuple[str, SimShipment]]] = {}
    for s in shipments:
        actions_by_ts.setdefault(s.created_at, []).append(("routed", s))
        actions_by_ts.setdefault(s.eta_can_tho, []).append(("arrived", s))

    start_ts = min(actions_by_ts)
    end_ts = max(s.eta_can_tho for s in shipments) + timedelta(hours=RESOLUTION_BUFFER_HOURS)

    checkpoints = set(actions_by_ts.keys())
    tick = start_ts
    while tick <= end_ts:
        checkpoints.add(tick)
        tick += timedelta(hours=TICK_HOURS)

    total_wait_cost = 0.0
    total_underfill_cost = 0.0
    safe_violation_count = 0
    dispatch_count = 0
    fill_ratios: list[float] = []
    wait_hours_list: list[float] = []

    for ts in sorted(checkpoints):
        still_out = []
        for return_ts, vehicle_id in pending_returns:
            if return_ts <= ts:
                vehicle = store.vehicles.get(vehicle_id)
                if vehicle is not None:
                    vehicle.status = VehicleStatus.AVAILABLE
            else:
                still_out.append((return_ts, vehicle_id))
        pending_returns = still_out

        for action, s in actions_by_ts.get(ts, []):
            if action == "routed":
                store.add_shipment(
                    Shipment(
                        shipment_id=s.shipment_id,
                        hub_id=s.hub_id,
                        commodity_id=s.commodity_id,
                        weight_kg=s.weight_kg,
                        selected_route=s.selected_route,
                        inbound_mode_to_can_tho=None,
                        outbound_mode_from_can_tho=s.outbound_mode,
                        created_at=s.created_at,
                        harvested_at=None,
                        eta_can_tho=s.eta_can_tho,
                    )
                )
            elif store.get_shipment(s.shipment_id) is not None:
                store.mark_arrived(s.shipment_id, ts, s.weight_kg)

        for mode in (Mode.ROAD, Mode.WATER):
            pending = store.pending_shipments(mode)
            if not pending:
                continue
            result = evaluate(store, ts, mode, config, ai2_data_dir)
            if result.decision != Decision.DISPATCH_NOW or result.selected_vehicle is None:
                continue

            ids = [p.shipment_id for p in pending]
            for p in pending:
                wait_hours = (ts - p.urgency_reference_ts).total_seconds() / 3600
                wait_hours_list.append(wait_hours)
                total_wait_cost += wait_hours * (p.effective_weight_kg / 1000) * WAIT_COST_PER_TON_HOUR

            underfill_ton = max(result.selected_vehicle.capacity_kg - result.current_load_kg, 0) / 1000
            total_underfill_cost += underfill_ton * UNDERFILL_COST_PER_TON
            fill_ratios.append(result.fill_ratio)
            if any(rc.value == "safe_wait_limit_reached" for rc in result.reason_codes):
                safe_violation_count += 1
            dispatch_count += 1
            store.mark_dispatched(ids, result.selected_vehicle.vehicle_id, ts)
            return_hours = round_trip_hours.get(mode, 12.0)
            pending_returns.append((ts + timedelta(hours=return_hours), result.selected_vehicle.vehicle_id))

    unresolved = store.pending_shipments()
    unresolved_cost = sum(
        ((end_ts - p.urgency_reference_ts).total_seconds() / 3600) * (p.effective_weight_kg / 1000) * UNRESOLVED_PENALTY_PER_TON_HOUR
        for p in unresolved
    )

    total_loss = total_wait_cost + total_underfill_cost + safe_violation_count * SAFE_VIOLATION_PENALTY + unresolved_cost

    return SimMetrics(
        total_loss=round(total_loss, 2),
        dispatch_count=dispatch_count,
        safe_violation_count=safe_violation_count,
        unresolved_count=len(unresolved),
        avg_fill_ratio=round(sum(fill_ratios) / len(fill_ratios), 4) if fill_ratios else 0.0,
        avg_wait_hours=round(sum(wait_hours_list) / len(wait_hours_list), 2) if wait_hours_list else 0.0,
    )


def run_simulation(
    shipments: list[SimShipment], config: DecisionConfig, ai2_data_dir=AI2_DATA_DIR
) -> SimMetrics:
    """Nhóm shipment theo tháng (`created_at`), chạy mỗi tháng như 1 episode độc lập, rồi cộng
    dồn kết quả — tránh sinh checkpoint rỗng giữa các tháng cách xa nhau (xem `_run_episode`)."""

    by_month: dict[str, list[SimShipment]] = {}
    for s in shipments:
        by_month.setdefault(s.created_at.strftime("%Y-%m"), []).append(s)

    episodes = [_run_episode(group, config, ai2_data_dir) for group in by_month.values() if group]
    if not episodes:
        return SimMetrics(0.0, 0, 0, 0, 0.0, 0.0)

    total_dispatch = sum(e.dispatch_count for e in episodes)
    total_fill_weighted = sum(e.avg_fill_ratio * e.dispatch_count for e in episodes)
    total_wait_events = sum(e.dispatch_count for e in episodes)  # avg_wait_hours weighted by dispatch batches
    total_wait_weighted = sum(e.avg_wait_hours * e.dispatch_count for e in episodes)

    return SimMetrics(
        total_loss=round(sum(e.total_loss for e in episodes), 2),
        dispatch_count=total_dispatch,
        safe_violation_count=sum(e.safe_violation_count for e in episodes),
        unresolved_count=sum(e.unresolved_count for e in episodes),
        avg_fill_ratio=round(total_fill_weighted / total_dispatch, 4) if total_dispatch else 0.0,
        avg_wait_hours=round(total_wait_weighted / total_wait_events, 2) if total_wait_events else 0.0,
    )


def grid_search(shipments: list[SimShipment]) -> list[dict]:
    # Lưới đúng theo AI2-plan.pdf mục 17.
    alphas = [0.40, 0.50, 0.55, 0.60]
    betas = [0.25, 0.30, 0.35, 0.40]
    gammas = [0.05, 0.10, 0.15, 0.20]
    thresholds = [0.65, 0.70, 0.75, 0.80, 0.85]

    combos = [
        (a, b, g)
        for a, b, g in itertools.product(alphas, betas, gammas)
        if abs(a + b + g - 1.0) < 1e-9
    ]

    results = []
    for alpha, beta, gamma in combos:
        for threshold in thresholds:
            config = DecisionConfig(alpha_fill=alpha, beta_urgency=beta, gamma_weather=gamma, dispatch_threshold=threshold)
            metrics = run_simulation(shipments, config)
            results.append(
                {
                    "alpha_fill": alpha,
                    "beta_urgency": beta,
                    "gamma_weather": gamma,
                    "dispatch_threshold": threshold,
                    **asdict(metrics),
                }
            )
    results.sort(key=lambda r: r["total_loss"])
    return results


def main() -> None:
    print("Loading Cần Thơ-bound shipments from real orders.csv via AI1 optimize_route()...")
    shipments = load_ct_bound_shipments()
    print(f"  {len(shipments)} shipments routed via Cần Thơ (out of orders in sample month).")

    print("Running grid search...")
    results = grid_search(shipments)
    print(f"  {len(results)} weight/threshold combinations evaluated.")

    report_path = Path(__file__).resolve().parents[1] / "reports" / "tuning_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now().isoformat(),
        "sample_months": ["2026-01", "2026-05", "2026-09"],
        "sample_size": len(shipments),
        "objective_note": "Proxy loss (wait cost/ton-hour + underfill cost/ton + safe-violation penalty + unresolved penalty). Not VND-denominated — see script docstring.",
        "top_10": results[:10],
        "current_default": next(
            (
                r
                for r in results
                if r["alpha_fill"] == 0.55 and r["beta_urgency"] == 0.35 and r["gamma_weather"] == 0.10 and r["dispatch_threshold"] == 0.75
            ),
            None,
        ),
        "all_results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTop 5 configs (by proxy total_loss, lower is better):")
    for r in results[:5]:
        print(
            f"  alpha={r['alpha_fill']} beta={r['beta_urgency']} gamma={r['gamma_weather']} "
            f"threshold={r['dispatch_threshold']} -> total_loss={r['total_loss']} "
            f"(dispatches={r['dispatch_count']}, avg_fill={r['avg_fill_ratio']}, "
            f"avg_wait_h={r['avg_wait_hours']}, safe_violations={r['safe_violation_count']}, "
            f"unresolved={r['unresolved_count']})"
        )

    if report["current_default"]:
        print(f"\nCurrent default (0.55/0.35/0.10, threshold=0.75): total_loss={report['current_default']['total_loss']}")

    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
