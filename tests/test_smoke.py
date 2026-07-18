"""Smoke test end-to-end cho AI2, dùng data thật (canonical v3). Chạy:

    cd VAIC-26-VinPaann
    python -m pytest ai2_dispatch/tests/test_smoke.py -v

Không mock data — cố tình dùng đúng commodity_id/hub_id/route enum thật để tự phát hiện lệch
schema sớm, thay vì để Backend phát hiện sau.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    # Reload để mỗi test module có StateStore sạch (module-level singleton trong main.py).
    import ai2_dispatch.app.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def _routed_event(event_id: str, shipment_id: str, weight_kg: float = 3000.0) -> dict:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "event_type": "shipment_routed_to_can_tho",
        "occurred_at": "2026-07-18T08:00:00+07:00",
        "shipment": {
            "shipment_id": shipment_id,
            "hub_id": "HUB_VINHLONG",
            "hub_name": "Hub Vĩnh Long",
            "commodity_id": "COM_VEGETABLE",
            "weight_kg": weight_kg,
            "selected_route": "via_can_tho_road_then_road",
            "inbound_mode_to_can_tho": "road",
            "outbound_mode_from_can_tho": "road",
            "created_at": "2026-07-18T08:00:00+07:00",
            "harvested_at": "2026-07-18T05:00:00+07:00",
            "eta_can_tho": "2026-07-18T11:30:00+07:00",
        },
    }


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_route_mode_mismatch_rejected(client: TestClient):
    bad = _routed_event("evt_bad", "shp_bad")
    bad["shipment"]["inbound_mode_to_can_tho"] = "water"  # không khớp via_can_tho_road_then_road
    resp = client.post("/api/v1/events/shipment-routed", json=bad)
    assert resp.status_code == 422


def test_shipment_lifecycle_and_dispatch_status(client: TestClient):
    routed = client.post("/api/v1/events/shipment-routed", json=_routed_event("evt_001", "shp_001"))
    assert routed.status_code == 200
    assert routed.json()["accepted"] is True

    # Duplicate event: không được cộng 2 lần.
    dup = client.post("/api/v1/events/shipment-routed", json=_routed_event("evt_001", "shp_001"))
    assert dup.json()["duplicate"] is True

    arrived = client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_002",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_001",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 2950.0,
        },
    )
    assert arrived.status_code == 200

    status = client.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T11:40:00+07:00"}
    )
    assert status.status_code == 200
    body = status.json()
    assert body["current_state"]["waiting_shipment_count"] == 1
    assert body["current_state"]["current_load_kg"] == pytest.approx(2950.0)
    assert body["decision"] in {"dispatch_now", "wait_for_load", "wait_for_vehicle"}
    print("dispatch-status:", body["decision"], body["reason_codes"], body["explanation"])


def test_unknown_shipment_arrived_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_999",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_999",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 100.0,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SHIPMENT_NOT_FOUND"


def test_forecast_endpoint_shape(client: TestClient):
    client.post("/api/v1/events/shipment-routed", json=_routed_event("evt_010", "shp_010", weight_kg=1500))
    resp = client.get("/api/v1/forecast", params={"outbound_mode": "road", "decision_ts": "2026-07-18T09:00:00+07:00"})
    assert resp.status_code == 200
    body = resp.json()
    assert "predicted_full_load" in body
    assert len(body["buckets"]) == int(body["config"]["horizon_hours"] * 60 / body["config"]["bucket_minutes"])


def test_dispatch_now_when_safe_wait_exceeded(client: TestClient):
    """COM_PANGASIUS: perishability_level=5 -> max_hold_hours=18h. harvested_at rất xa quá khứ
    -> phải dispatch_now dù chưa đầy tải (hard constraint 3)."""

    event = _routed_event("evt_020", "shp_020", weight_kg=200)
    event["shipment"]["commodity_id"] = "COM_PANGASIUS"
    event["shipment"]["harvested_at"] = "2026-07-01T00:00:00+07:00"  # rất lâu trước decision_ts
    client.post("/api/v1/events/shipment-routed", json=event)
    client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_021",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_020",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 200.0,
        },
    )
    status = client.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T11:40:00+07:00"}
    )
    body = status.json()
    assert body["decision"] == "dispatch_now"
    assert "safe_wait_limit_reached" in body["reason_codes"]
