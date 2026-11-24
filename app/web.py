"""Shared web helpers: templates, flash messages, CSRF, login/role dependencies."""
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from . import clock, repo
from .config import get_settings
from .security import csrf_matches, new_csrf_token

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _money(value) -> str:
    return f"{get_settings().currency} {float(value or 0):,.2f}"


def _dt(value) -> str:
    return clock.parse(value).strftime("%a %d %b %Y, %H:%M") if value else ""


def _time(value) -> str:
    return clock.parse(value).strftime("%H:%M") if value else ""


def _input_dt(value) -> str:
    return clock.parse(value).strftime("%Y-%m-%dT%H:%M") if value else ""


templates.env.filters.update({"money": _money, "dt": _dt, "tm": _time, "inputdt": _input_dt})


class RedirectTo(Exception):
    def __init__(self, url: str):
        self.url = url


def go(url: str) -> RedirectResponse:
    """303 redirect used after every POST (post/redirect/get)."""
    return RedirectResponse(url, status_code=303)


def get_system(request: Request):
    return request.app.state.system


def flash(request: Request, message: str, level: str = "info") -> None:
    request.session.setdefault("_flash", []).append([level, message])


def get_csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = new_csrf_token()
    return request.session["csrf"]


def verify_csrf(request: Request, submitted: str | None) -> None:
    if not csrf_matches(request.session.get("csrf"), submitted):
        raise HTTPException(status_code=403, detail="Security check failed (CSRF token). Reload the page and try again.")


def current_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        return None
    return repo.get_user(get_system(request).db, uid)


def login_required(request: Request):
    user = current_user(request)
    if not user:
        raise RedirectTo("/login?next=" + request.url.path)
    return user


def role_required(*roles: str):
    def dependency(request: Request):
        user = login_required(request)
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to open this page.")
        return user

    return dependency


admin_required = role_required("admin")
staff_required = role_required("staff", "admin")


def render(request: Request, name: str, status_code: int = 200, **context):
    user = current_user(request)
    db = get_system(request).db
    context.update(
        user=user,
        csrf_token=get_csrf_token(request),
        flashes=request.session.pop("_flash", []),
        unread=repo.unread_count(db, user["id"]) if user else 0,
        now=clock.now(),
    )
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err["loc"] if not isinstance(p, int))
    return f"{field}: {err['msg']}" if field else err["msg"]


def to_number(text, cast=float):
    try:
        return cast(text) if str(text).strip() != "" else None
    except ValueError:
        return None


def safe_next(target: str, default: str = "/") -> str:
    return target if target.startswith("/") and not target.startswith("//") else default
