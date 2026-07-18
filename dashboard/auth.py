from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .config.users import USERS


router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")


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
