"""Agentic periodic tick — vòng lặp "quan sát → dự báo → quyết định → lặp lại" chạy độc lập,
không cần request để trigger.

1 background task tick định kỳ, tự đánh giá lại quyết định cho cả 2 outbound_mode, và log khi quyết định đổi.

Tách riêng `run_single_tick()` (đồng bộ, dễ test) khỏi `periodic_tick_loop()` (async, chạy vô
hạn)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from . import decision_engine
from .data_loader import DEFAULT_DATA_DIR
from .enums import Decision, Mode
from .state_store import StateStore

logger = logging.getLogger("ai2_dispatch.agent")

TICK_SECONDS = float(os.environ.get("AI2_AGENT_TICK_SECONDS", "30"))


def run_single_tick(
    store: StateStore,
    config: decision_engine.DecisionConfig,
    decision_ts: datetime | None = None,
) -> dict[Mode, decision_engine.DecisionResult]:
    """1 chu kỳ quan sát -> dự báo -> quyết định cho từng outbound_mode đang có shipment chờ.
    Bỏ qua mode không có gì để tránh log rác."""

    ts = decision_ts or datetime.now(timezone.utc)
    results: dict[Mode, decision_engine.DecisionResult] = {}
    for mode in (Mode.ROAD, Mode.WATER):
        if not store.pending_shipments(mode):
            continue
        results[mode] = decision_engine.evaluate(store, ts, mode, config, DEFAULT_DATA_DIR)
    return results


async def periodic_tick_loop(
    store: StateStore,
    config: decision_engine.DecisionConfig,
    tick_seconds: float = TICK_SECONDS,
) -> None:
    last_decision: dict[Mode, Decision] = {}
    logger.info("Agent tick loop started (interval=%.0fs)", tick_seconds)
    while True:
        try:
            results = run_single_tick(store, config)
            for mode, result in results.items():
                if last_decision.get(mode) != result.decision:
                    logger.info(
                        "[agent tick] outbound_mode=%s decision=%s reason_codes=%s "
                        "fill_ratio=%.0f%% waiting=%d :: %s",
                        mode.value,
                        result.decision.value,
                        [rc.value for rc in result.reason_codes],
                        result.fill_ratio * 100,
                        result.waiting_shipment_count,
                        result.explanation,
                    )
                    last_decision[mode] = result.decision
        except Exception:  # noqa: BLE001 - agent loop không được phép chết vì 1 lần tick lỗi
            logger.exception("Agent tick failed, will retry next interval")
        await asyncio.sleep(tick_seconds)
