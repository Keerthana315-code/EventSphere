"""Public ticket verification page - the page a phone opens after scanning a ticket QR code.

Anonymous visitors see event details and whether the ticket is valid (holder name masked, no e-mail).
Logged-in staff/admin also see the full holder name and can admit the guest with one button.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .. import services
from ..web import current_user, flash, get_system, go, render, staff_required, verify_csrf

router = APIRouter()


def _mask(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return " ".join(p[0] + "*" * (len(p) - 1) if i else p for i, p in enumerate(parts)) or "Guest"


def _load(request, code):
    row = get_system(request).db.one(
        "SELECT t.id, t.code, t.status, t.used_at, t.event_id, k.name AS category_name, e.title, e.start_time, "
        "e.end_time, e.status AS event_status, v.name AS venue_name, u.name AS holder "
        "FROM tickets t JOIN ticket_categories k ON k.id=t.category_id JOIN events e ON e.id=t.event_id "
        "JOIN venues v ON v.id=e.venue_id JOIN users u ON u.id=t.user_id WHERE t.code=:c", c=code,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return row


@router.get("/verify/{code}")
def verify_page(request: Request, code: str):
    ticket = _load(request, code)
    user = current_user(request)
    is_staff = bool(user and user["role"] in ("staff", "admin"))
    holder = ticket["holder"] if is_staff else _mask(ticket["holder"])
    return render(request, "verify.html", ticket=ticket, holder=holder, is_staff=is_staff)


@router.post("/verify/{code}/admit")
async def verify_admit(request: Request, code: str, csrf_token: str = Form(""), user=Depends(staff_required)):
    verify_csrf(request, csrf_token)
    ticket = _load(request, code)
    result = await run_in_threadpool(services.scan_ticket, get_system(request), user["id"], code, ticket["event_id"])
    if result.get("ok"):
        flash(request, "ADMIT - ticket checked in.", "success")
    else:
        flash(request, "REJECT: " + str(result.get("reason", "not valid")), "danger")
    return go(f"/verify/{code}")
