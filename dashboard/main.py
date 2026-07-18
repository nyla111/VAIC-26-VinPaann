from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router
from .routers.dashboard import router as dashboard_router


app = FastAPI(title="VAIC Logistics Dashboard")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("DASHBOARD_SECRET_KEY", "vaic-hackathon-session-secret"),
    same_site="lax",
    https_only=os.getenv("DASHBOARD_COOKIE_HTTPS", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
app.include_router(auth_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return RedirectResponse("/dashboard", status_code=303)
