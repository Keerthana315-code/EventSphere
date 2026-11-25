"""Attendee pages: booking, tickets, cancellation, waitlist, notifications, private hire."""
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .. import clock, repo, rules, services
from ..clock import parse
from ..schemas import HireIn
from ..web import first_error, flash, get_system, go, login_required, render, verify_csrf

router = APIRouter()


# ------------------------------------------------------------------ booking
@router.post("/events/{event_id}/book")
async def book(request: Request, event_id: int, user=Depends(login_required)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    items = []
    for key, value in form.multi_items():
        if key.startswith("qty_") and key[4:].isdigit() and str(value).isdigit() and int(value) > 0:
            items.append({"category_id": int(key[4:]), "qty": int(value)})
    system = get_system(request)
    result = await run_in_threadpool(services.book, system, user["id"], event_id, items, bool(form.get("simulate_failure")))
    if result["ok"]:
        c = result["content"]
        flash(request, f"Booking confirmed! {c['count']} ticket(s), payment reference {c['payment_ref']}.", "success")
        return go("/my/bookings")
    flash(request, result["reason"], "danger")
    return go(f"/events/{event_id}")


@router.get("/my/bookings")
def my_bookings(request: Request, user=Depends(login_required)):
    db = get_system(request).db
    bookings = repo.user_bookings(db, user["id"])
    now = clock.now()
    for b in bookings:
        hours = (parse(b["start_time"]) - now).total_seconds() / 3600
        b["can_cancel"] = b["status"] == "confirmed" and hours > 0
        b["refund_preview"] = rules.refund_percent(hours) if hours > 0 else 0
    return render(request, "my_bookings.html", bookings=bookings, waitlist=repo.user_waitlist(db, user["id"]),
                  policy=rules.REFUND_POLICY_TEXT)


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(request: Request, booking_id: int, csrf_token: str = Form(""), user=Depends(login_required)):
    verify_csrf(request, csrf_token)
    result = services.cancel_booking(get_system(request), user["id"], booking_id)
    if result["ok"]:
        c = result["content"]
        flash(request, f"Booking cancelled. Refund: {c['refund']:,.2f} ({c['percent']}%).", "success")
    else:
        flash(request, result["reason"], "danger")
    return go("/my/bookings")


# ------------------------------------------------------------------ tickets
def _own_ticket(request, code, user):
    ticket = get_system(request).db.one(
        "SELECT t.*, k.name AS category_name, e.title, e.start_time, e.end_time, v.name AS venue_name, e.status AS event_status "
        "FROM tickets t JOIN ticket_categories k ON k.id=t.category_id JOIN events e ON e.id=t.event_id "
        "JOIN venues v ON v.id=e.venue_id WHERE t.code=:c", c=code,
    )
    if not ticket or ticket["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@router.get("/tickets/{code}")
def ticket_page(request: Request, code: str, user=Depends(login_required)):
    return render(request, "ticket.html", ticket=_own_ticket(request, code, user))


@router.get("/tickets/{code}/qr.png")
def ticket_qr(request: Request, code: str, user=Depends(login_required)):
    import qrcode  # any Python QR library is allowed

    _own_ticket(request, code, user)
    # The QR holds a link, so a phone camera opens the ticket page; the gate scanner extracts the code from it.
    base = request.app.state.settings.public_base_url
    if not base:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
        base = f"{proto}://{host}"
    buffer = io.BytesIO()
    qrcode.make(f"{base}/verify/{code}", box_size=8, border=2).save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


# ----------------------------------------------------------------- waitlist
@router.post("/events/{event_id}/waitlist")
def join_waitlist(request: Request, event_id: int, category_id: int = Form(...), quantity: int = Form(1),
                  csrf_token: str = Form(""), user=Depends(login_required)):
    verify_csrf(request, csrf_token)
    result = services.join_waitlist(get_system(request), user["id"], event_id, category_id, quantity)
    if result["ok"]:
        flash(request, f"You are on the waitlist (position {result['content']['position']}). We will notify you when seats free up.", "success")
    else:
        flash(request, result["reason"], "danger")
    return go(f"/events/{event_id}")


@router.post("/waitlist/{entry_id}/claim")
def claim(request: Request, entry_id: int, simulate_failure: str = Form(""), csrf_token: str = Form(""), user=Depends(login_required)):
    verify_csrf(request, csrf_token)
    result = services.claim_offer(get_system(request), user["id"], entry_id, bool(simulate_failure))
    flash(request, "Seats claimed - your tickets are ready!" if result["ok"] else result["reason"], "success" if result["ok"] else "danger")
    return go("/my/bookings")


@router.post("/waitlist/{entry_id}/leave")
def leave(request: Request, entry_id: int, csrf_token: str = Form(""), user=Depends(login_required)):
    verify_csrf(request, csrf_token)
    result = services.leave_waitlist(get_system(request), user["id"], entry_id)
    flash(request, "You left the waitlist." if result["ok"] else result["reason"], "info" if result["ok"] else "danger")
    return go("/my/bookings")


# ------------------------------------------------------------ notifications
@router.get("/notifications")
def notifications(request: Request, user=Depends(login_required)):
    db = get_system(request).db
    rows = db.query("SELECT * FROM notifications WHERE user_id=:u ORDER BY id DESC LIMIT 100", u=user["id"])
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=:u AND is_read=0", u=user["id"])
    return render(request, "notifications.html", items=rows)


# -------------------------------------------------------------- private hire
@router.get("/hire")
def hire_form(request: Request, user=Depends(login_required)):
    venues = [v for v in repo.list_venues(get_system(request).db) if v["open_for_hire"]]
    return render(request, "hire.html", venues=venues)


@router.post("/hire")
def hire_submit(request: Request, venue_id: str = Form(""), start: str = Form(""), end: str = Form(""),
                guests: str = Form(""), purpose: str = Form(""), csrf_token: str = Form(""), user=Depends(login_required)):
    verify_csrf(request, csrf_token)
    system = get_system(request)
    venues = [v for v in repo.list_venues(system.db) if v["open_for_hire"]]
    try:
        data = HireIn(venue_id=venue_id, start=start, end=end, guests=guests, purpose=purpose)
    except ValidationError as exc:
        flash(request, first_error(exc), "danger")
        return render(request, "hire.html", status_code=422, venues=venues, form=dict(venue_id=venue_id, start=start, end=end, guests=guests, purpose=purpose))
    result = services.request_hire(system, user["id"], data.venue_id, data.start, data.end, data.guests, data.purpose)
    return render(request, "hire_result.html", result=result, form=data.model_dump(), venues={v["id"]: v for v in venues})


@router.get("/hire/mine")
def my_hires(request: Request, user=Depends(login_required)):
    return render(request, "hire_mine.html", hires=repo.user_hires(get_system(request).db, user["id"]))
