from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS
from app.database import create_db_and_tables
from app.routes.layer1 import router as layer1_router
from app.routes.hub import router as hub_router
from app.routes.layer2 import router as layer2_router
from app.routes.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    Initializes SQLite schemas and settings values.
    """
    create_db_and_tables()
    yield

app = FastAPI(
    title="Mekong Delta Agri-Logistics Orchestrator API",
    description="Asynchronous backend orchestrating agricultural shipments with 2-Layer AI routing and event-driven dispatch loop.",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(layer1_router, prefix="/api/layer1", tags=["Layer 1 Route Optimizer"])
app.include_router(hub_router, prefix="/api/hub", tags=["Hub Operations"])
app.include_router(layer2_router, prefix="/api/layer2", tags=["Layer 2 Dispatch & Forecast"])
app.include_router(ws_router, tags=["Real-time Dashboard (WebSockets)"])


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
