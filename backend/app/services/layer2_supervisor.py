"""Process-local Layer 2 supervisor.

Commands remain REST/WebSocket operations, while this task continuously
evaluates the durable SQLite state and publishes resulting state events.
"""

from __future__ import annotations

import asyncio
import logging

from app.state import state_manager

logger = logging.getLogger(__name__)


async def run_layer2_supervisor(stop_event: asyncio.Event, interval_seconds: float = 5.0) -> None:
    while not stop_event.is_set():
        try:
            state, dispatched = await state_manager.evaluate_and_dispatch()
            if dispatched:
                from app.routes.websocket import ws_manager

                await ws_manager.broadcast(state)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed model cycle must not kill the supervisor or the API.
            logger.exception("Layer 2 supervisor cycle failed")
            try:
                state = await state_manager.record_ai_error("supervisor cycle failed; previous state retained")
                from app.routes.websocket import ws_manager

                await ws_manager.broadcast_event("AI_ERROR", state)
            except Exception:
                logger.exception("Failed to publish Layer 2 stale-state error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
