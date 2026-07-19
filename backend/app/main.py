from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.config import CORS_ORIGINS
from app.database import create_db_and_tables
from app.routes.layer1 import router as layer1_router
from app.routes.hub import router as hub_router
from app.routes.layer2 import router as layer2_router
from app.routes.websocket import router as ws_router
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.logistics import router as logistics_router
from app.routes.orders import router as orders_router
from app.routes.simulation import router as simulation_router
from app.simulation import run_simulation_loop
from app.services.layer2_supervisor import run_layer2_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    Initializes SQLite schemas and settings values.
    """
    create_db_and_tables()
    stop_event = asyncio.Event()
    sim_loop = asyncio.create_task(run_simulation_loop(stop_event))
    layer2_loop = asyncio.create_task(run_layer2_supervisor(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        sim_loop.cancel()
        layer2_loop.cancel()
        await asyncio.gather(sim_loop, layer2_loop, return_exceptions=True)

app = FastAPI(
    title="Mekong Delta Agri-Logistics Orchestrator API",
    description="Asynchronous backend orchestrating agricultural shipments with 2-Layer AI routing and event-driven dispatch loop.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure Session Middleware for signed cookie sessions
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("DASHBOARD_SECRET_KEY", "vaic-hackathon-session-secret"),
    same_site="lax",
    https_only=os.getenv("DASHBOARD_COOKIE_HTTPS", "false").lower() == "true",
)

# Configure CORS for React integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # Set to False when using wildcard allow_origins ("*")
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(simulation_router, tags=["Simulation Config"])
app.include_router(layer1_router, prefix="/api/layer1", tags=["Layer 1 Route Optimizer"])
app.include_router(hub_router, prefix="/api/hub", tags=["Hub Operations"])
app.include_router(layer2_router, prefix="/api/layer2", tags=["Layer 2 Dispatch & Forecast"])
app.include_router(ws_router, tags=["Real-time Dashboard (WebSockets)"])
app.include_router(auth_router, tags=["Dashboard Auth"])
app.include_router(logistics_router, tags=["Logistics Provider Portal"])
app.include_router(orders_router, tags=["Role-scoped Orders"])

app.include_router(dashboard_router, tags=["Dashboard View/Operations"])



@app.get("/")
async def root_endpoint():
    """
    Root status landing endpoint showing system meta details.
    """
    return {
        "project": "Mekong Delta Agri-Logistics Orchestrator",
        "region": "Đồng bằng sông Cửu Long (ĐBSCL) to HCMC",
        "architecture": "2-Layer AI Consolidation Loop",
        "docs_url": "/docs",
        "status": "Operational"
    }
