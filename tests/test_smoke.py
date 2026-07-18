"""Smoke test end-to-end cho AI2, dùng data thật (canonical v3). Chạy:

    cd VAIC-26-VinPaann
    python -m pytest ai2_dispatch/tests/test_smoke.py -v

"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # State giờ persist ra file (xem state_store.py); mỗi test cần 1 file riêng qua
    # AI2_STATE_FILE, nếu không sẽ đọc lại state từ lần chạy trước và test sẽ nhiễu nhau.
    monkeypatch.setenv("AI2_STATE_FILE", str(tmp_path / "ai2_state_test.pkl"))
    # TestClient() không dùng làm context manager thì lifespan (agent tick) không tự chạy, nhưng
    # tắt tường minh cho chắc — test không cần vòng lặp nền chạy song song.
    monkeypatch.setenv("AI2_DISABLE_AGENT_TICK", "1")
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


def test_ai1_route_code_accepted_without_explicit_modes(client: TestClient):
    """Quyết định: AI2 tự normalize route code A-E của AI1 và tự suy ra inbound/outbound mode
    nếu Backend không gửi — không cần chờ ai làm bước convert trước."""

    event = {
        "schema_version": "1.0",
        "event_id": "evt_030",
        "event_type": "shipment_routed_to_can_tho",
        "occurred_at": "2026-07-18T08:00:00+07:00",
        "shipment": {
            "shipment_id": "shp_030",
            "hub_id": "HUB_VINHLONG",
            "commodity_id": "COM_VEGETABLE",
            "weight_kg": 1000,
            "selected_route": "B_ROAD_VIA_CT",  # route code AI1, không phải enum AI2
            "created_at": "2026-07-18T08:00:00+07:00",
            "eta_can_tho": "2026-07-18T11:30:00+07:00",
        },
    }
    resp = client.post("/api/v1/events/shipment-routed", json=event)
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] is True


def test_direct_route_rejected(client: TestClient):
    event = _routed_event("evt_031", "shp_031")
    event["shipment"]["selected_route"] = "A_DIRECT_ROAD"
    event["shipment"]["inbound_mode_to_can_tho"] = None
    event["shipment"]["outbound_mode_from_can_tho"] = "road"
    resp = client.post("/api/v1/events/shipment-routed", json=event)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ROUTE_NOT_APPLICABLE"


def test_unknown_commodity_falls_back_instead_of_crashing(client: TestClient):
    event = _routed_event("evt_040", "shp_040", weight_kg=800)
    event["shipment"]["commodity_id"] = "COM_DOES_NOT_EXIST"
    client.post("/api/v1/events/shipment-routed", json=event)
    client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_041",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_040",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 800.0,
        },
    )
    status = client.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T11:40:00+07:00"}
    )
    assert status.status_code == 200
    assert status.json()["current_state"]["waiting_shipment_count"] == 1


def test_state_survives_restart(tmp_path, monkeypatch):
    state_file = tmp_path / "persisted_state.pkl"
    monkeypatch.setenv("AI2_STATE_FILE", str(state_file))

    import ai2_dispatch.app.main as main_module

    importlib.reload(main_module)
    client1 = TestClient(main_module.app)
    client1.post("/api/v1/events/shipment-routed", json=_routed_event("evt_050", "shp_050"))
    assert state_file.exists()

    # "Restart" service: reload module lại với CÙNG state file.
    importlib.reload(main_module)
    client2 = TestClient(main_module.app)
    status = client2.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T09:00:00+07:00"}
    )
    # Shipment vẫn ở state routed_to_can_tho (chưa arrived) nên chưa tính vào current_load,
    # nhưng phải còn tồn tại trong state -> in_transit list được forecast dùng.
    forecast = client2.get(
        "/api/v1/forecast", params={"outbound_mode": "road", "decision_ts": "2026-07-18T09:00:00+07:00"}
    ).json()
    total_known = sum(b["known_inbound_kg"] for b in forecast["buckets"])
    assert total_known > 0, "shipment routed trước restart phải vẫn xuất hiện trong known inbound sau restart"


def test_dispatch_completed_removes_shipment_from_pending_pool(client: TestClient):
    client.post("/api/v1/events/shipment-routed", json=_routed_event("evt_060", "shp_060", weight_kg=1200))
    client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_061",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_060",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 1200.0,
        },
    )
    before = client.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T11:40:00+07:00"}
    ).json()
    assert before["current_state"]["waiting_shipment_count"] == 1

    resp = client.post(
        "/api/v1/events/dispatch-completed",
        json={
            "schema_version": "1.0",
            "event_id": "evt_062",
            "event_type": "dispatch_completed",
            "occurred_at": "2026-07-18T11:45:00+07:00",
            "shipment_ids": ["shp_060"],
            "vehicle_id": before["selected_vehicle"]["vehicle_id"],
            "actual_departure_at": "2026-07-18T11:45:00+07:00",
        },
    )
    assert resp.status_code == 200

    after = client.get(
        "/api/v1/dispatch-status", params={"outbound_mode": "road", "decision_ts": "2026-07-18T11:50:00+07:00"}
    ).json()
    assert after["current_state"]["waiting_shipment_count"] == 0


def test_agent_run_single_tick_reflects_live_state(client: TestClient):
    """Phần agentic (app/agent.py): run_single_tick() phải thấy đúng state hiện tại của
    StateStore singleton trong main module, không phải state riêng — vì đây chính là cái vòng
    lặp nền sẽ đọc khi chạy thật."""

    import ai2_dispatch.app.main as main_module
    from ai2_dispatch.app.agent import run_single_tick
    from ai2_dispatch.app.enums import Mode

    client.post("/api/v1/events/shipment-routed", json=_routed_event("evt_070", "shp_070", weight_kg=900))
    client.post(
        "/api/v1/events/shipment-arrived",
        json={
            "schema_version": "1.0",
            "event_id": "evt_071",
            "event_type": "shipment_arrived_can_tho",
            "occurred_at": "2026-07-18T11:35:00+07:00",
            "shipment_id": "shp_070",
            "actual_arrival_at": "2026-07-18T11:35:00+07:00",
            "actual_weight_kg": 900.0,
        },
    )

    from datetime import datetime, timezone

    results = run_single_tick(
        main_module.store,
        main_module.DEFAULT_CONFIG,
        decision_ts=datetime(2026, 7, 18, 11, 40, tzinfo=timezone.utc),
    )
    assert Mode.ROAD in results
    assert results[Mode.ROAD].waiting_shipment_count == 1
    # Không có shipment water nào -> mode đó bị bỏ qua, không log rác.
    assert Mode.WATER not in results


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
