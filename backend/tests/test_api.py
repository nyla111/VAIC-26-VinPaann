import os

# Override database URL to use an isolated test database before importing main app
os.environ["DATABASE_URL"] = "sqlite:///test_agri.db"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from app.main import app
from app.database import engine

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Setup test database tables
    SQLModel.metadata.create_all(engine)
    yield
    # Teardown: drop all tables and delete test db file
    SQLModel.metadata.drop_all(engine)
    if os.path.exists("test_agri.db"):
        os.remove("test_agri.db")


def test_root_endpoint():
    # Set CWD properly in env if needed by model loader
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Operational"
    assert "project" in data


def test_layer1_optimize_valid():
    payload = {
        "hub_id": "HUB_VINHLONG",
        "commodity_id": "COM_VEGETABLE",
        "loai_hang": "rau_mau",
        "khoi_luong_kg": 3495.7,
        "timestamp": "2026-01-01T09:58:52+07:00",
        "deadline_ts": "2026-01-01T23:27:12+07:00"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 200
    result = response.json()
    
    assert result["hub_id"] == "HUB_VINHLONG"
    assert "priority" in result
    assert result["priority"]["tier"] == "vegetable"
    assert "phuong_an" in result
    assert len(result["phuong_an"]) == 5
    
    # Assert fields are present in each option
    for route in result["phuong_an"]:
        assert "route_code" in route
        assert "ten" in route
        assert "trang_thai" in route
        assert "chi_phi_du_doan_vnd" in route
        assert "thoi_gian_du_kien_gio" in route

    # There should be a recommended route recommended_route
    assert "recommended_route" in result
    assert result["recommended_route"] is not None


def test_layer1_optimize_invalid():
    # Invalid Hub ID (value error map)
    payload = {
        "hub_id": "HUB_UNKNOWN",
        "commodity_id": "COM_VEGETABLE",
        "loai_hang": "rau_mau",
        "khoi_luong_kg": 3495.7,
        "timestamp": "2026-01-01T09:58:52+07:00"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 400
    assert "Unknown hub_id" in response.json()["detail"]

    # Negative Volume (Pydantic ValidationError > gt=0)
    payload = {
        "hub_id": "HUB_VINHLONG",
        "commodity_id": "COM_VEGETABLE",
        "loai_hang": "rau_mau",
        "khoi_luong_kg": -50.0,
        "timestamp": "2026-01-01T09:58:52+07:00"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 422


def test_hub_select_route_and_state():
    # 1. Verify initial status
    status_response = client.get("/api/hub/status")
    assert status_response.status_code == 200
    state = status_response.json()
    assert state["inventory"]["vegetable"] == 0.0
    assert state["dispatch_status"] == "WAIT"

    # 2. Select direct route (A_DIRECT_ROAD should not accumulate cargo in Can Tho hub)
    payload_direct = {
        "hub_id": "HUB_VINHLONG",
        "selected_route_id": "A_DIRECT_ROAD",
        "cargo_type": "vegetable",
        "volume": 1500.0,
        "weather": "Clear"
    }
    response_direct = client.post("/api/hub/select-route", json=payload_direct)
    assert response_direct.status_code == 200
    
    status_response = client.get("/api/hub/status")
    state_after_direct = status_response.json()
    assert state_after_direct["inventory"]["vegetable"] == 0.0 # Bypassed Can Tho

    # 3. Select Can Tho route (B_ROAD_VIA_CT should accumulate cargo in Can Tho hub)
    payload_cantho = {
        "hub_id": "HUB_VINHLONG",
        "selected_route_id": "B_ROAD_VIA_CT",
        "cargo_type": "vegetable",
        "volume": 2000.0,
        "weather": "Clear"
    }
    response_cantho = client.post("/api/hub/select-route", json=payload_cantho)
    assert response_cantho.status_code == 200
    
    status_response = client.get("/api/hub/status")
    state_after_cantho = status_response.json()
    assert state_after_cantho["inventory"]["vegetable"] == 2000.0 # Accumulated in kg


def test_simulate_incoming():
    response = client.post("/api/hub/simulate-incoming")
    assert response.status_code == 202
    data = response.json()
    assert "Simulation Event Triggered" in data["message"]
    assert "cargo_details" in data
    assert "optimized_decision" in data


def test_websocket_connection():
    with client.websocket_connect("/ws/status") as websocket:
        # Receive initial state frame
        data = websocket.receive_json()
        assert "inventory" in data
        assert "dispatch_status" in data
        assert "weather" in data
        assert "logs" in data

