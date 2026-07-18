from datetime import datetime
from sqlmodel import Session, SQLModel, create_engine, select
from app.config import DATABASE_URL, CARGO_TYPES
from app.models import CargoInventory, SystemSettings, Vehicle
from app.ai.forecast_dispatch.data_loader import get_fleet_bootstrap_rows

# SQLite connection args for multi-threaded async frameworks
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

def create_db_and_tables():
    """
    Initializes SQLModel schemas on SQLite database.
    """
    SQLModel.metadata.create_all(engine)
    init_db_defaults()

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
        users_in_db = session.exec(select(User)).first()
        if not users_in_db:
            session.add(User(email="enterprise1@vaic.vn", password_hash="demo123", role="enterprise"))
            session.add(User(email="logistics1@vaic.vn", password_hash="demo123", role="logistics"))
            session.add(User(email="admin1@vaic.vn", password_hash="demo123", role="admin"))

        
        # Seed vehicles from fleet.csv bootstrap if database is empty
        vehicles_in_db = session.exec(select(Vehicle)).first()
        if not vehicles_in_db:
            try:
                bootstrap_rows = get_fleet_bootstrap_rows()
                for row in bootstrap_rows:
                    # Parse available date/time safely
                    avail_dt = row["_available_dt"]
                    avail_str = avail_dt.isoformat() if isinstance(avail_dt, datetime) else str(avail_dt)
                    
                    v = Vehicle(
                        vehicle_id=row["vehicle_id"],
                        mode=row["mode"],
                        capacity_kg=float(row["capacity_ton"]) * 1000.0,
                        status=row["status"],
                        available_from=avail_str,
                        supports_refrigeration=bool(row["has_reefer"]),
                        location="can_tho"
                    )
                    session.add(v)
            except Exception as e:
                # Fallback to prevent crash if fleet.csv load fails
                print(f"Error bootstrapping fleet: {e}")
        
        session.commit()

