from typing import Dict, List, Optional
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, SQLModel
from app.ai.route_optimizer.schemas import RouteOptimizeRequest, RouteOptimizeResponse, RouteCode, PhuongAn

# ----------------- SQLModel Database Tables -----------------

class CargoInventory(SQLModel, table=True):
    """
    Tracks inventory of different cargo tiers consolidated at Can Tho Hub (in kg).
    """
    cargo_type: str = Field(primary_key=True)
    volume: float = Field(default=0.0)


class SystemLog(SQLModel, table=True):
    """
    Maintains historical logs of orchestration decisions, sensor updates, and simulations.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: str
    message: str


class SystemSettings(SQLModel, table=True):
    """
    Tracks key-value config attributes like active_weather and dispatch_status.
    """
    key: str = Field(primary_key=True)
    value: str


class User(SQLModel, table=True):
    """
    User accounts for authentication and authorization.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: str  # "enterprise", "logistics", "admin"


class Order(SQLModel, table=True):
    """
    Stores details of agricultural orders created dynamically by users/customers.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    hub_id: str
    commodity_id: Optional[str] = None
    loai_hang: Optional[str] = ""
    khoi_luong_kg: float
    timestamp: str
    deadline_ts: Optional[str] = None
    created_at: str
    
    # Layer 2 trip tracking fields
    selected_route_id: Optional[str] = None
    state: str = Field(default="created")
    actual_arrival_at: Optional[str] = None
    actual_weight_kg: Optional[float] = None

    # New enterprise role fields
    delivery_deadline: Optional[str] = None
    harvested_at: Optional[str] = None
    assigned_vehicle_id: Optional[str] = None
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    dispatched_at: Optional[str] = None



class Vehicle(SQLModel, table=True):
    """
    Tracks vehicle state and refrigeration features consolidated at Can Tho Hub.
    """
    vehicle_id: str = Field(primary_key=True)
    mode: str
    capacity_kg: float
    status: str
    available_from: str
    supports_refrigeration: bool = False
    location: str = "can_tho"


# ----------------- API Request & Response Schemas -----------------

# optimize API schemas are imported directly from app.ai.route_optimizer.schemas:
# - RouteOptimizeRequest
# - RouteOptimizeResponse

class RouteSelectRequest(BaseModel):
    hub_id: str = PydanticField(..., description="Local hub name (canonical ID)")
    selected_route_id: str = PydanticField(..., description="Selected route option ID (RouteCode)")
    cargo_type: str = PydanticField(..., description="Type of cargo (tier: seafood, vegetable, etc.)")
    volume: float = PydanticField(..., description="Weight in kg")
    weather: Optional[str] = PydanticField("Clear", description="Active weather condition")
    order_id: Optional[str] = PydanticField(None, description="Optional ID of the order being selected")



class SystemState(BaseModel):
    inventory: Dict[str, float] = PydanticField(..., description="Can Tho accumulated inventory map (in kg)")
    dispatch_status: str = PydanticField(..., description="WAIT or DISPATCH")
    weather: str = PydanticField(..., description="Global weather condition")
    logs: List[Dict[str, str]] = PydanticField(..., description="Latest activity logs")
    last_updated: str = PydanticField(..., description="Timestamp of the last state change")

