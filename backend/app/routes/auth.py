from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import engine
from app.models import User

router = APIRouter(prefix="/api/v1/auth")


class LoginPayload(BaseModel):
    email: str
    password: str


def current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    role = request.session.get("role")
    if not user_id or not role:
        return None
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user or user.role != role:
            request.session.clear()
            return None
        return user


@router.get("/session")
def api_session(request: Request):
    user = current_user(request)
    if user is None:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role
        }
    }


@router.post("/login")
async def api_login(request: Request, payload: LoginPayload):
    email = payload.email
    password = payload.password

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or user.password_hash != password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sai email hoặc mật khẩu."
            )
        
        request.session["user_id"] = user.id
        request.session["role"] = user.role
        request.session["username"] = user.email

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        }


@router.post("/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}
