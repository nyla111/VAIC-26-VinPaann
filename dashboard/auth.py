from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .config.users import USERS


router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")


class LoginPayload(BaseModel):
    username: str
    password: str


def _model_from_dict(model_cls, data: dict[str, Any]):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def current_user(request: Request) -> dict[str, Any] | None:
    username = request.session.get("username")
    role = request.session.get("role")
    if not username or not role:
        return None
    user = USERS.get(username)
    if not user or user["role"] != role:
        request.session.clear()
        return None
    return {"username": username, "role": role, "name": user.get("name", username)}


def require_user(request: Request) -> dict[str, Any] | RedirectResponse:
    user = current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return user


@router.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = USERS.get(username)
    if not user or user["password"] != password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Sai username hoặc password."},
            status_code=401,
        )
    request.session["username"] = username
    request.session["role"] = user["role"]
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/dashboard/api/session")
def api_session(request: Request):
    user = current_user(request)
    return {"authenticated": user is not None, "user": user}


@router.post("/dashboard/api/login")
async def api_login(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = _model_from_dict(LoginPayload, await request.json())
        username = payload.username
        password = payload.password
    else:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

    user = USERS.get(username)
    if not user or user["password"] != password:
        return JSONResponse({"error": "Sai username hoặc password."}, status_code=401)
    request.session["username"] = username
    request.session["role"] = user["role"]
    return {"user": {"username": username, "role": user["role"], "name": user.get("name", username)}}


@router.post("/dashboard/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}
