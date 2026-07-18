from typing import List
from fastapi import APIRouter, HTTPException, status
from app.config import CARGO_TYPES, HUBS, WEATHER_CONDITIONS
from app.models import OptimizeRequest, RouteOption
from app.ai.layer1_helper import predict_routes

router = APIRouter()

@router.post("/optimize", response_model=List[RouteOption], status_code=status.HTTP_200_OK)
async def optimize_route(request: OptimizeRequest):
    """
    Evaluates cargo transportation parameters and returns 3 optimized routing options.
    """
    # Validate inputs
    if request.hub_id not in HUBS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hub_id '{request.hub_id}'. Supported hubs: {HUBS}"
        )
        
    if request.cargo_type not in CARGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cargo_type '{request.cargo_type}'. Supported cargo: {CARGO_TYPES}"
        )

    if request.volume <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Volume must be greater than 0 tons."
        )

    if request.urgency_level not in ["Low", "Medium", "High"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Urgency level must be one of: Low, Medium, High."
        )

    if request.weather not in WEATHER_CONDITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid weather condition '{request.weather}'. Supported: {WEATHER_CONDITIONS}"
        )

    # Calculate routes
    try:
        routes = predict_routes(
            hub_id=request.hub_id,
            cargo_type=request.cargo_type,
            volume=request.volume,
            urgency_level=request.urgency_level,
            weather=request.weather
        )
        return routes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute route prediction models: {str(e)}"
        )
