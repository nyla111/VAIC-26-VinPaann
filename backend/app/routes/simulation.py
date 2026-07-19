from fastapi import APIRouter, Body
from pydantic import BaseModel
import app.simulation as sim

router = APIRouter(prefix="/api/v1/simulation")

class SimulationConfig(BaseModel):
    time_acceleration_factor: int

@router.post("/config")
async def update_simulation_config(config: SimulationConfig):
    """
    Mutates the global simulation acceleration factor.
    """
    sim.TIME_ACCELERATION_FACTOR = config.time_acceleration_factor
    return {
        "status": "success",
        "time_acceleration_factor": sim.TIME_ACCELERATION_FACTOR,
        "system_clock": sim.SYSTEM_CLOCK.isoformat()
    }
