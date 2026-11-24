from fastapi import APIRouter, Form, Request
from pydantic import ValidationError

from .. import repo
from ..schemas import RegisterIn
from ..security import verify_password
from ..web import current_user, first_error, flash, get_system, go, render, safe_next, verify_csrf

router = APIRouter()

HOME = {"admin": "/admin", "staff": "/staff/scan", "attendee": "/"}


@router.get("/login")
def login_form(request: Request, next: str = "/"):
    return render(request, "login.html", next=safe_next(next))


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/"), csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = repo.get_user_by_email(get_system(request).db, email)
    if not user or not verify_password(password, user["password_hash"]):
        flash(request, "Wrong email or password.", "danger")
        return render(request, "login.html", status_code=401, next=safe_next(next))
    request.session.clear()  # new session on login (prevents session fixation)
    request.session["uid"] = user["id"]
    target = safe_next(next, "")
    return go(target if target not in ("", "/") else HOME.get(user["role"], "/"))


@router.get("/register")
def register_form(request: Request):
    return render(request, "register.html")


@router.post("/register")
def register(request: Request, name: str = Form(""), email: str = Form(""), password: str = Form(""), csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    db = get_system(request).db
    try:
        data = RegisterIn(name=name, email=email, password=password)
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return render(request, "register.html", status_code=422, form={"name": name, "email": email})
    if repo.get_user_by_email(db, data.email):
        flash(request, "That email is already registered. Try signing in.", "danger")
        return render(request, "register.html", status_code=409, form={"name": name, "email": email})
    user_id = repo.create_user(db, data.name, data.email, data.password, "attendee")  # public sign-up is always an attendee
    request.session.clear()
    request.session["uid"] = user_id
    flash(request, "Welcome to EventSphere! Your account is ready.", "success")
    return go("/")


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    request.session.clear()
    return go("/login")


@router.get("/healthz")
def healthz(request: Request):
    get_system(request).db.scalar("SELECT 1")
    return {"status": "ok", "user": bool(current_user(request))}
