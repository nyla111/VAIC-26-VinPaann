from typing import Dict, List, Optional
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, SQLModel

# ----------------- SQLModel Database Tables -----------------

class CargoInventory(SQLModel, table=True):
    """
    Tracks inventory of different cargo types consolidated at Can Tho Hub.
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

# ----------------- API Request & Response Schemas -----------------

class OptimizeRequest(BaseModel):
    hub_id: str = PydanticField(..., description="Local hub name (e.g., An Giang, Hau Giang)")
    cargo_type: str = PydanticField(..., description="Type of cargo (Fruit, Vegetable, Seafood)")
    volume: float = PydanticField(..., description="Weight in tons")
    urgency_level: str = PydanticField(..., description="Low, Medium, or High")
    weather: Optional[str] = PydanticField("Clear", description="Weather context (Clear, Rainy, Stormy)")


class RouteOption(BaseModel):
    route_id: str = PydanticField(..., description="Unique identifier for the option")
    route_name: str = PydanticField(..., description="Human-readable route name")
    estimated_cost: float = PydanticField(..., description="ETA-dependent transportation cost")
    eta: float = PydanticField(..., description="Estimated arrival time in hours")
    recommendation_flag: bool = PydanticField(..., description="True if recommended by Layer 1 AI")
    reason: str = PydanticField(..., description="Contextual explanation for the recommendation")


class RouteSelectRequest(BaseModel):
    hub_id: str = PydanticField(..., description="Local hub name")
    selected_route_id: str = PydanticField(..., description="Selected route option ID")
    cargo_type: str = PydanticField(..., description="Type of cargo")
    volume: float = PydanticField(..., description="Weight in tons")
    weather: Optional[str] = PydanticField("Clear", description="Active weather condition")


class SystemState(BaseModel):
    inventory: Dict[str, float] = PydanticField(..., description="Can Tho accumulated inventory map")
    dispatch_status: str = PydanticField(..., description="WAIT or DISPATCH")
    weather: str = PydanticField(..., description="Global weather condition")
    logs: List[Dict[str, str]] = PydanticField(..., description="Latest activity logs")
    last_updated: str = PydanticField(..., description="Timestamp of the last state change")
