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


class SystemState(BaseModel):
    inventory: Dict[str, float] = PydanticField(..., description="Can Tho accumulated inventory map (in kg)")
    dispatch_status: str = PydanticField(..., description="WAIT or DISPATCH")
    weather: str = PydanticField(..., description="Global weather condition")
    logs: List[Dict[str, str]] = PydanticField(..., description="Latest activity logs")
    last_updated: str = PydanticField(..., description="Timestamp of the last state change")

