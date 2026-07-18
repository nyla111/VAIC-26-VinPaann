from __future__ import annotations

from fastapi import FastAPI

from .optimizer import optimize_route
from .schemas import RouteOptimizeRequest, RouteOptimizeResponse


app = FastAPI(title="Layer AI 1 - Route & Cost Optimizer")


@app.post("/api/v1/route-optimize", response_model=RouteOptimizeResponse)
def route_optimize(payload: RouteOptimizeRequest) -> dict:
    if hasattr(payload, "model_dump"):
        return optimize_route(payload.model_dump())
    return optimize_route(payload.dict())
