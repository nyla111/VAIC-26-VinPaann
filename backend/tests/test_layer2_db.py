import os

# Override database URL to use an isolated test database before importing main app
os.environ["DATABASE_URL"] = "sqlite:///test_agri.db"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.database import engine
from app.models import Vehicle, Order

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Setup test database tables and seed defaults (including fleet bootstrap)
    from app.database import create_db_and_tables
    create_db_and_tables()
    yield
    # Teardown: drop all tables cleanly
    from sqlmodel import SQLModel
    SQLModel.metadata.drop_all(engine)



def test_fleet_bootstrap():
    """
    Ensure the 77-car fleet (at Can Tho Hub) was automatically seeded into the database on startup.
    """
    with Session(engine) as session:
        vehicles = session.exec(select(Vehicle)).all()
        assert len(vehicles) > 0
        # Ensure properties are mapped correctly
        for v in vehicles:
            assert v.location == "can_tho"
            assert v.capacity_kg > 0
            assert v.status in ["available", "en_route", "maintenance", "reserved"]


def test_layer2_routed_and_automatic_arrival():
    """
    Ensures that selecting a Can Tho route with small volume transitions the order
    automatically into arrived_waiting state (FastAPI TestClient runs background tasks synchronously).
    """
    # 1. Select a route passing through Can Tho (volume 50.0 kg is small enough to avoid instant dispatch)
    payload = {
        "hub_id": "HUB_VINHLONG",
        "selected_route_id": "B_ROAD_VIA_CT",
        "cargo_type": "vegetable",
        "volume": 50.0,
        "weather": "Clear"
    }
    response = client.post("/api/hub/select-route", json=payload)
    assert response.status_code == 200
    
    # 2. Check the order was created and has already transitioned to arrived_waiting
    # (since FastAPI TestClient executes background tasks synchronously before returning)
    with Session(engine) as session:
        order = session.exec(select(Order).where(Order.selected_route_id == "B_ROAD_VIA_CT")).first()
        assert order is not None
        assert order.state == "arrived_waiting"
        assert order.actual_arrival_at is not None
        assert order.actual_weight_kg == 50.0


def test_layer2_endpoints():
    """
    Tests Layer 2 forecast and dispatch status queries.
    """
    # Query dispatch status for ROAD pipeline
    response = client.get("/api/layer2/dispatch-status?outbound_mode=road")
    assert response.status_code == 200
    data = response.json()
    assert "decision" in data
    assert "current_state" in data
    assert data["current_state"]["waiting_shipment_count"] > 0
    
    # Query forecast
    response_fc = client.get("/api/layer2/forecast?outbound_mode=road")
    assert response_fc.status_code == 200
    fc_data = response_fc.json()
    assert "predicted_full_load" in fc_data
    assert "buckets" in fc_data
