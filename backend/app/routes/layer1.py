from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session
from app.database import engine
from app.models import Order, RouteOptimizeRequest, RouteOptimizeResponse
from app.ai.route_optimizer.optimizer import optimize_route

router = APIRouter()


@router.post("/optimize", response_model=RouteOptimizeResponse, status_code=status.HTTP_200_OK)
async def optimize_route_endpoint(request: RouteOptimizeRequest):
    """
    Evaluates agricultural cargo transportation parameters, saves the order in SQLite, and returns optimized routing options.
    """
    try:
        # 1. Save the new order dynamically to the SQLite database
        with Session(engine) as session:
            new_order = Order(
                hub_id=request.hub_id,
                commodity_id=request.commodity_id,
                loai_hang=request.loai_hang or "",
                khoi_luong_kg=request.khoi_luong_kg,
                timestamp=request.timestamp,
                deadline_ts=request.deadline_ts,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            session.add(new_order)
            session.commit()
            session.refresh(new_order)
            order_id = str(new_order.id)

        # 2. Execute the actual Layer 1 optimizer model using the order_id from database
        payload_dict = request.model_dump()
        payload_dict["order_id"] = order_id
        
        result = optimize_route(payload_dict)
        # Ensure order_id is returned in the response
        result["order_id"] = order_id
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute route prediction models: {str(e)}"
        )

