from sqlmodel import Session, SQLModel, create_engine, select
from app.config import DATABASE_URL, CARGO_TYPES
from app.models import CargoInventory, SystemSettings

# SQLite connection args for multi-threaded async frameworks
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
    Seeds default system configurations and initial cargo states if not present.
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
        
        session.commit()
