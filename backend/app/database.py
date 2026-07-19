import json
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine, select
from app.config import DATABASE_URL, CARGO_TYPES
from app.models import CargoInventory, SystemSettings, Vehicle, Order, DispatchOrder
from app.ai.forecast_dispatch.data_loader import get_fleet_bootstrap_rows

# SQLite connection args for multi-threaded async frameworks
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

def _migrate_vehicle_table() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        # Check if table vehicle exists and has vehicle_id column
        columns = [row[1] for row in connection.exec_driver_sql('PRAGMA table_info("vehicle")').fetchall()]
        if columns and "vehicle_id" in columns:
            # Drop old tables to avoid conflicts and force clean schema recreation
            connection.exec_driver_sql('DROP TABLE IF EXISTS "dispatchorder"')
            connection.exec_driver_sql('DROP TABLE IF EXISTS "vehicle"')

def create_db_and_tables():
    """
    Initializes SQLModel schemas on SQLite database.
    """
    _migrate_vehicle_table()
    SQLModel.metadata.create_all(engine)
    _ensure_order_columns()
    _normalize_vehicle_available_from()
    init_db_defaults()


def _ensure_order_columns() -> None:
    """Small SQLite migration for hackathon deployments using an existing DB file.

    SQLModel's ``create_all`` creates new tables but does not add columns to an
    already-created table. These additive columns are deliberately nullable so
    existing orders remain readable during rollout.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    table_columns = {
        "order": {
        "harvested_at": "TEXT",
        "assigned_provider_id": "INTEGER",
        "provider_assignment_status": "TEXT DEFAULT 'unassigned'",
        "provider_assigned_at": "TEXT",
        "route_options_json": "TEXT",
        "selected_route_cost_vnd": "FLOAT",
        "selected_route_eta_hours": "FLOAT",
        "selected_route_geometry_json": "TEXT",
        "optimizer_version": "TEXT",
        "predicted_full_load_time": "TEXT",
        "reason_codes_json": "TEXT",
        "priority_score_json": "TEXT",
        "dispatch_proposal_id": "TEXT",
        "eta_can_tho": "TEXT",
        },
        "systemlog": {
            "event_type": "TEXT",
            "payload_json": "TEXT",
            "level": "TEXT DEFAULT 'INFO'",
        },
        "dispatchorder": {
            "eta_hcm": "TEXT",
        }
    }
    with engine.begin() as connection:
        for table, columns in table_columns.items():
            existing = {
                row[1]
                for row in connection.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
            }
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
        connection.exec_driver_sql(
            'UPDATE "order" SET "harvested_at" = "created_at" '
            'WHERE "harvested_at" IS NULL OR TRIM("harvested_at") = ""'
        )
        # Existing orders that already have an outbound vehicle can be scoped
        # to that vehicle's logistics provider immediately.  New workflow
        # code may assign a provider before assigning a vehicle.
        connection.exec_driver_sql(
            'UPDATE "order" SET "assigned_provider_id" = '
            '(SELECT "provider_id" FROM "vehicle" '
            ' WHERE "vehicle"."license_plate" = "order"."assigned_vehicle_id"), '
            '"provider_assignment_status" = \'assigned\' '
            'WHERE "assigned_provider_id" IS NULL '
            'AND "assigned_vehicle_id" IS NOT NULL '
            'AND EXISTS (SELECT 1 FROM "vehicle" '
                        'WHERE "vehicle"."license_plate" = "order"."assigned_vehicle_id")'
        )
        connection.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_order_user_id" ON "order" ("user_id")'
        )
        connection.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_order_assigned_provider_id" '
            'ON "order" ("assigned_provider_id")'
        )
        connection.exec_driver_sql(
            'CREATE INDEX IF NOT EXISTS "ix_order_provider_assignment_status" '
            'ON "order" ("provider_assignment_status")'
        )


def _normalize_vehicle_available_from() -> None:
    """Interpret legacy naive fleet timestamps as the application's ICT time.

    Older bootstrap rows used ``datetime.now().isoformat()`` without an
    offset. Layer 2 compares them with UTC-aware timestamps, which made
    available vehicles look like they were not available yet.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    ict = timezone(timedelta(hours=7))
    with Session(engine) as session:
        changed = False
        for vehicle in session.exec(select(Vehicle)).all():
            if not vehicle.available_from:
                continue
            try:
                available_from = datetime.fromisoformat(vehicle.available_from)
            except ValueError:
                continue
            if available_from.tzinfo is None:
                vehicle.available_from = available_from.replace(tzinfo=ict).isoformat()
                session.add(vehicle)
                changed = True
        if changed:
            session.commit()

def init_db_defaults():
    """
    Seeds default system configurations, initial cargo states, and fleet bootstrap if not present.
    """
    with Session(engine) as session:
        # Seed default weather
        weather_setting = session.get(SystemSettings, "weather")
        if not weather_setting:
            session.add(SystemSettings(key="weather", value="Clear"))
        
        # Seed default dispatch status
        dispatch_setting = session.get(SystemSettings, "dispatch_status")
        if not dispatch_setting:
            session.add(SystemSettings(key="dispatch_status", value="WAIT"))

        # Seed cargo inventory categories
        for cargo in CARGO_TYPES:
            inv = session.get(CargoInventory, cargo)
            if not inv:
                session.add(CargoInventory(cargo_type=cargo, volume=0.0))
        
        # Seed default users
        from app.models import User
        
        # Seed admin
        if not session.exec(select(User).where(User.email == "admin1@vaic.vn")).first():
            session.add(User(email="admin1@vaic.vn", password_hash="demo123", role="admin"))
            
        # Seed enterprise users
        for i in range(1, 6):
            email = f"enterprise{i}@vaic.vn"
            if not session.exec(select(User).where(User.email == email)).first():
                session.add(User(email=email, password_hash="demo123", role="enterprise"))
                
        # Seed logistics users
        logistics_ids = {}
        for i in range(1, 6):
            email = f"logistics{i}@vaic.vn"
            u = session.exec(select(User).where(User.email == email)).first()
            if not u:
                u = User(email=email, password_hash="demo123", role="logistics")
                session.add(u)
                session.commit()
                session.refresh(u)
            logistics_ids[i] = u.id
        
        session.commit()

        # Seed vehicles with realistic Vietnamese plates, coordinates and provider ID distributed
        vehicles_in_db = session.exec(select(Vehicle)).first()
        if not vehicles_in_db:
            seed_vehicles = [
                # Provider 1: Mekong Logistics
                {"license_plate": "65C-123.45", "mode": "road", "capacity_kg": 5000.0, "status": "available", "location": "can_tho", "current_lat": 10.03, "current_lng": 105.78, "supports_refrigeration": True, "p_idx": 1},
                {"license_plate": "65C-088.99", "mode": "road", "capacity_kg": 8000.0, "status": "available", "location": "can_tho", "current_lat": 10.04, "current_lng": 105.79, "supports_refrigeration": True, "p_idx": 1},
                
                # Provider 2: Southern Freight
                {"license_plate": "64C-456.78", "mode": "road", "capacity_kg": 5000.0, "status": "available", "location": "can_tho", "current_lat": 10.25, "current_lng": 105.97, "supports_refrigeration": False, "p_idx": 2},
                {"license_plate": "83C-789.01", "mode": "road", "capacity_kg": 15000.0, "status": "available", "location": "can_tho", "current_lat": 9.60, "current_lng": 105.97, "supports_refrigeration": False, "p_idx": 2},
                
                # Provider 3: Delta Waterway
                {"license_plate": "SG-9876", "mode": "water", "capacity_kg": 200000.0, "status": "available", "location": "can_tho", "current_lat": 10.05, "current_lng": 105.80, "supports_refrigeration": False, "p_idx": 3},
                {"license_plate": "SG-4321", "mode": "water", "capacity_kg": 500000.0, "status": "available", "location": "can_tho", "current_lat": 10.06, "current_lng": 105.81, "supports_refrigeration": False, "p_idx": 3},
                
                # Provider 4: Cần Thơ Trans
                {"license_plate": "CT-8888", "mode": "water", "capacity_kg": 50000.0, "status": "available", "location": "can_tho", "current_lat": 10.15, "current_lng": 106.10, "supports_refrigeration": False, "p_idx": 4},
                {"license_plate": "VL-1111", "mode": "water", "capacity_kg": 200000.0, "status": "available", "location": "can_tho", "current_lat": 10.26, "current_lng": 105.98, "supports_refrigeration": False, "p_idx": 4},
                
                # Provider 5: An Giang Transport
                {"license_plate": "67C-234.56", "mode": "road", "capacity_kg": 15000.0, "status": "available", "location": "can_tho", "current_lat": 10.37, "current_lng": 105.43, "supports_refrigeration": False, "p_idx": 5},
                {"license_plate": "51C-987.65", "mode": "road", "capacity_kg": 15000.0, "status": "maintenance", "location": "can_tho", "current_lat": 10.02, "current_lng": 105.76, "supports_refrigeration": True, "p_idx": 5},
                {"license_plate": "50H-112.34", "mode": "road", "capacity_kg": 8000.0, "status": "available", "location": "can_tho", "current_lat": 10.03, "current_lng": 105.77, "supports_refrigeration": True, "p_idx": 5},
            ]
            
            for sv in seed_vehicles:
                v = Vehicle(
                    license_plate=sv["license_plate"],
                    provider_id=logistics_ids[sv["p_idx"]],
                    mode=sv["mode"],
                    capacity_kg=sv["capacity_kg"],
                    status=sv["status"],
                    available_from=datetime.now(timezone.utc).isoformat(),
                    supports_refrigeration=sv["supports_refrigeration"],
                    location=sv["location"],
                    current_lat=sv["current_lat"],
                    current_lng=sv["current_lng"]
                )
                session.add(v)
            session.commit()

        # Seed default orders if none exist
        orders_in_db = session.exec(select(Order)).first()
        if not orders_in_db:
            # Let's seed a few orders
            o1 = Order(
                id=101,
                hub_id="HUB_VINHLONG",
                commodity_id="COM_RICE",
                loai_hang="Gạo",
                khoi_luong_kg=4500.0,
                timestamp=datetime.now().isoformat(),
                created_at=datetime.now().isoformat(),
                state="arrived_waiting"
            )
            o2 = Order(
                id=102,
                hub_id="HUB_SOCTRANG",
                commodity_id="COM_SHRIMP",
                loai_hang="Tôm",
                khoi_luong_kg=12000.0,
                timestamp=datetime.now().isoformat(),
                created_at=datetime.now().isoformat(),
                state="dispatched"
            )
            o3 = Order(
                id=103,
                hub_id="HUB_LONGXUYEN",
                commodity_id="COM_VEGETABLE",
                loai_hang="Rau củ",
                khoi_luong_kg=8500.0,
                timestamp=datetime.now().isoformat(),
                created_at=datetime.now().isoformat(),
                state="dispatched"
            )
            session.add(o1)
            session.add(o2)
            session.add(o3)
            session.commit()

        # Seed default dispatch orders (Jobs) if none exist
        dispatches_in_db = session.exec(select(DispatchOrder)).first()
        if not dispatches_in_db:
            d1 = DispatchOrder(
                proposal_id="proposal_seed_001",
                vehicle_id="83C-789.01",
                outbound_mode="road",
                shipment_ids_json=json.dumps(["102"]),
                total_weight_kg=12000.0,
                capacity_kg=15000.0,
                fill_ratio=0.8,
                status="moving_to_can_tho",
                created_at=datetime.now().isoformat(),
                dispatched_at=datetime.now().isoformat()
            )
            d2 = DispatchOrder(
                proposal_id="proposal_seed_002",
                vehicle_id="CT-8888",
                outbound_mode="water",
                shipment_ids_json=json.dumps(["103"]),
                total_weight_kg=8500.0,
                capacity_kg=50000.0,
                fill_ratio=0.17,
                status="consolidating_at_can_tho",
                created_at=datetime.now().isoformat(),
                dispatched_at=datetime.now().isoformat()
            )
            session.add(d1)
            session.add(d2)
            session.commit()
