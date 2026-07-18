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
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Operational"
    assert "project" in data


def test_layer1_optimize_valid():
    payload = {
        "hub_id": "An Giang",
        "cargo_type": "Fruit",
        "volume": 12.5,
        "urgency_level": "Medium",
        "weather": "Clear"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 3
    
    # Assert fields are present
    for route in routes:
        assert "route_id" in route
        assert "route_name" in route
        assert "estimated_cost" in route
        assert "eta" in route
        assert "recommendation_flag" in route
        assert "reason" in route

    # Exactly one route should be recommended
    recs = [r for r in routes if r["recommendation_flag"]]
    assert len(recs) == 1


def test_layer1_optimize_invalid():
    # Invalid Cargo Type
    payload = {
        "hub_id": "An Giang",
        "cargo_type": "Meat", # Invalid
        "volume": 12.5,
        "urgency_level": "Medium",
        "weather": "Clear"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 400
    assert "Invalid cargo_type" in response.json()["detail"]

    # Negative Volume
    payload = {
        "hub_id": "An Giang",
        "cargo_type": "Fruit",
        "volume": -5.0, # Invalid
        "urgency_level": "Medium",
        "weather": "Clear"
    }
    response = client.post("/api/layer1/optimize", json=payload)
    assert response.status_code == 400


def test_hub_select_route_and_state():
    # 1. Verify initial status
    status_response = client.get("/api/hub/status")
    assert status_response.status_code == 200
    state = status_response.json()
    assert state["inventory"]["Fruit"] == 0.0
    assert state["dispatch_status"] == "WAIT"

    # 2. Select direct route (should not accumulate cargo in Can Tho hub)
    payload_direct = {
        "hub_id": "Hau Giang",
        "selected_route_id": "direct_road",
        "cargo_type": "Fruit",
        "volume": 15.0,
        "weather": "Clear"
    }
    response_direct = client.post("/api/hub/select-route", json=payload_direct)
    assert response_direct.status_code == 200
    
    status_response = client.get("/api/hub/status")
    state_after_direct = status_response.json()
    assert state_after_direct["inventory"]["Fruit"] == 0.0 # Bypassed Can Tho

    # 3. Select Can Tho route (should accumulate cargo in Can Tho hub)
    payload_cantho = {
        "hub_id": "An Giang",
        "selected_route_id": "cantho_road",
        "cargo_type": "Fruit",
        "volume": 20.0,
        "weather": "Clear"
    }
    response_cantho = client.post("/api/hub/select-route", json=payload_cantho)
    assert response_cantho.status_code == 200
    
    status_response = client.get("/api/hub/status")
    state_after_cantho = status_response.json()
    assert state_after_cantho["inventory"]["Fruit"] == 20.0 # Accumulated


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
