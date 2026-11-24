"""Admin / organiser pages. Every route depends on admin_required (role check)."""
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .. import repo, rules, services
from ..schemas import EventIn, RegisterIn, VenueIn
from ..web import admin_required, first_error, flash, get_system, go, render, verify_csrf

router = APIRouter(prefix="/admin")


# ---------------------------------------------------------------- dashboard
@router.get("")
def dashboard(request: Request, user=Depends(admin_required)):
    return render(request, "admin/dashboard.html", data=repo.dashboard(get_system(request).db))


@router.post("/sweep")
def run_sweep(request: Request, csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    result = get_system(request).sweep()
    flash(request, f"WaitlistAgent sweep done: {result.content.get('expired', 0)} hold(s) expired, "
                   f"{result.content.get('reoffered', 0)} seat(s) re-offered.", "success")
    return go("/admin/messages")


# ------------------------------------------------------------------- venues
def _venue_data(name, location, capacity, description, image_url, hourly_rate, open_for_hire) -> VenueIn:
    return VenueIn(name=name, location=location, capacity=capacity, description=description,
                   image_url=image_url, hourly_rate=hourly_rate, open_for_hire=bool(open_for_hire))


@router.get("/venues")
def venues(request: Request, user=Depends(admin_required)):
    return render(request, "admin/venues.html", venues=repo.list_venues(get_system(request).db), form={})


@router.post("/venues")
def venue_create(request: Request, name: str = Form(""), location: str = Form(""), capacity: str = Form(""),
                 description: str = Form(""), image_url: str = Form(""), hourly_rate: str = Form("0"),
                 open_for_hire: str = Form(""), csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    db = get_system(request).db
    try:
        data = _venue_data(name, location, capacity, description, image_url, hourly_rate, open_for_hire)
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return render(request, "admin/venues.html", status_code=422, venues=repo.list_venues(db),
                      form=dict(name=name, location=location, capacity=capacity, description=description,
                                image_url=image_url, hourly_rate=hourly_rate, open_for_hire=open_for_hire))
    repo.create_venue(db, data.model_dump())
    flash(request, f"Venue '{data.name}' created.", "success")
    return go("/admin/venues")


@router.get("/venues/{venue_id}")
def venue_edit_form(request: Request, venue_id: int, user=Depends(admin_required)):
    venue = repo.get_venue(get_system(request).db, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found.")
    return render(request, "admin/venue_edit.html", venue=venue)


@router.post("/venues/{venue_id}")
def venue_edit(request: Request, venue_id: int, name: str = Form(""), location: str = Form(""), capacity: str = Form(""),
               description: str = Form(""), image_url: str = Form(""), hourly_rate: str = Form("0"),
               open_for_hire: str = Form(""), csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    db = get_system(request).db
    if not repo.get_venue(db, venue_id):
        raise HTTPException(status_code=404, detail="Venue not found.")
    try:
        data = _venue_data(name, location, capacity, description, image_url, hourly_rate, open_for_hire)
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return go(f"/admin/venues/{venue_id}")
    error = repo.update_venue(db, venue_id, data.model_dump())
    flash(request, error or "Venue saved.", "danger" if error else "success")
    return go(f"/admin/venues/{venue_id}" if error else "/admin/venues")


# ------------------------------------------------------------------- events
@router.get("/events")
def events(request: Request, user=Depends(admin_required)):
    return render(request, "admin/events.html", events=repo.admin_events(get_system(request).db))


@router.get("/events/new")
def event_new_form(request: Request, user=Depends(admin_required)):
    return render(request, "admin/event_new.html", venues=repo.list_venues(get_system(request).db),
                  categories=rules.EVENT_CATEGORIES, form={}, suggestions=None)


@router.post("/events/new")
async def event_new(request: Request, user=Depends(admin_required)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    system = get_system(request)
    names, prices, quantities = form.getlist("cat_name"), form.getlist("cat_price"), form.getlist("cat_qty")
    cats = [{"name": n, "price": p or "0", "quantity": q} for n, p, q in zip(names, prices, quantities) if n.strip()]
    raw = {k: form.get(k, "") for k in ("title", "category", "venue_id", "start", "end", "description")}
    context = dict(venues=repo.list_venues(system.db), categories=rules.EVENT_CATEGORIES, suggestions=None,
                   form={**raw, "cats": cats})
    try:
        data = EventIn(**raw, categories=cats, publish=form.get("action") == "publish")
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return render(request, "admin/event_new.html", status_code=422, **context)
    result = await run_in_threadpool(
        services.create_event, system, admin_id=user["id"], title=data.title, category=data.category,
        venue_id=data.venue_id, start=data.start, end=data.end, description=data.description,
        categories=[c.model_dump() for c in data.categories], publish=data.publish)
    if not result["ok"]:  # VenueAgent refused: show its reason and its alternatives
        flash(request, "VenueAgent refused this slot: " + result["reason"], "danger")
        context["suggestions"] = result.get("suggestions")
        return render(request, "admin/event_new.html", status_code=409, **context)
    flash(request, "Event published." if data.publish else "Event saved as a draft.", "success")
    return go("/admin/events")


@router.post("/events/{event_id}/publish")
def event_publish(request: Request, event_id: int, csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    result = services.publish_event(get_system(request), event_id)
    flash(request, "Event published." if result["ok"] else result["reason"], "success" if result["ok"] else "danger")
    return go("/admin/events")


@router.post("/events/{event_id}/cancel")
def event_cancel(request: Request, event_id: int, reason: str = Form(""), csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    result = services.cancel_event(get_system(request), event_id, reason)
    if result["ok"]:
        c = result["content"]
        flash(request, f"Event cancelled. {c['refunded_bookings']} booking(s) refunded in full ({c['refunded_total']:,.2f}).", "success")
    else:
        flash(request, result["reason"], "danger")
    return go("/admin/events")


@router.post("/events/{event_id}/delete")
def event_delete(request: Request, event_id: int, csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    result = services.delete_draft(get_system(request), event_id)
    flash(request, "Draft deleted." if result["ok"] else result["reason"], "success" if result["ok"] else "danger")
    return go("/admin/events")


# ------------------------------------------------------------- private hire
@router.get("/hires")
def hires(request: Request, user=Depends(admin_required)):
    rows = get_system(request).db.query(
        "SELECT h.*, v.name AS venue_name, u.name AS user_name FROM hire_requests h JOIN venues v ON v.id=h.venue_id "
        "JOIN users u ON u.id=h.user_id WHERE h.status <> 'declined' ORDER BY (h.status='pending') DESC, h.id DESC")
    return render(request, "admin/hires.html", hires=rows)


@router.post("/hires/{hire_id}/decide")
def hire_decide(request: Request, hire_id: int, decision: str = Form(""), note: str = Form(""),
                csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    result = services.decide_hire(get_system(request), user["id"], hire_id, decision == "approve", note)
    flash(request, f"Request {result['content'].get('status')}." if result["ok"] else result["reason"],
          "success" if result["ok"] else "danger")
    return go("/admin/hires")


# ------------------------------------------------------ agent message log
@router.get("/messages")
def messages(request: Request, conversation: str = "", user=Depends(admin_required)):
    db = get_system(request).db
    if conversation:
        rows = db.query("SELECT * FROM messages WHERE conversation_id=:c ORDER BY id", c=conversation)
    else:
        rows = db.query("SELECT * FROM messages ORDER BY id DESC LIMIT 150")
    for r in rows:
        r["pretty"] = json.dumps(json.loads(r["content"]), indent=None, ensure_ascii=False)
    return render(request, "admin/messages.html", messages=rows, conversation=conversation, states=repo.agent_states(db))


# -------------------------------------------------------------------- users
@router.get("/users")
def users(request: Request, user=Depends(admin_required)):
    rows = get_system(request).db.query("SELECT id, name, email, role, created_at FROM users ORDER BY id")
    return render(request, "admin/users.html", users=rows)


@router.post("/users")
def user_create(request: Request, name: str = Form(""), email: str = Form(""), password: str = Form(""),
                role: str = Form("staff"), csrf_token: str = Form(""), user=Depends(admin_required)):
    verify_csrf(request, csrf_token)
    db = get_system(request).db
    if role not in ("staff", "admin"):
        role = "staff"
    try:
        data = RegisterIn(name=name, email=email, password=password)
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return go("/admin/users")
    if repo.get_user_by_email(db, data.email):
        flash(request, "That email already exists.", "danger")
    else:
        repo.create_user(db, data.name, data.email, data.password, role)
        flash(request, f"{role.title()} account created for {data.email}.", "success")
    return go("/admin/users")
