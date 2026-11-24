"""Use-case orchestration for the web layer: every business decision is delegated to an agent
through the message bus. These functions only prepare the request and shape the answer."""
from . import clock
from .bus import Performative, new_conversation_id
from .clock import fmt, parse

UI = "WebUI"  # the "sender" name used in the message log for user actions


def _answer(reply) -> dict:
    """Turn an agent reply into a simple dict the routes can show to the user."""
    p = reply.performative
    return {
        "ok": p in (Performative.AGREE, Performative.INFORM),
        "performative": p.value,
        "reason": reply.content.get("reason", ""),
        "content": reply.content,
        "conversation_id": reply.conversation_id,
    }


def create_event(system, *, admin_id, title, category, venue_id, start, end, description, categories, publish) -> dict:
    """Save an event (draft or published). VenueAgent decides whether the time slot is free."""
    db, conv = system.db, new_conversation_id()
    total = sum(c["quantity"] for c in categories)
    if not categories:
        return {"ok": False, "reason": "Add at least one ticket category."}
    event_id = db.insert(
        "INSERT INTO events(title, category, venue_id, start_time, end_time, description, status, created_by, created_at) "
        "VALUES (:t, :c, :v, :s, :e, :d, 'draft', :a, :n)",
        t=title, c=category, v=venue_id, s=fmt(parse(start)), e=fmt(parse(end)), d=description, a=admin_id, n=fmt(clock.now()),
    )
    reply = system.bus.request(
        UI, "VenueAgent", "reserve_slot", conv, venue_id=venue_id, start=start, end=end,
        tickets_total=total, ref_id=event_id, kind="event",
    )
    if reply.performative != Performative.AGREE:
        db.execute("DELETE FROM events WHERE id=:i", i=event_id)
        out = _answer(reply)
        out["suggestions"] = reply.content.get("suggestions", {})
        return out
    for c in categories:
        db.insert(
            "INSERT INTO ticket_categories(event_id, name, price, quantity) VALUES (:e, :n, :p, :q)",
            e=event_id, n=c["name"], p=c["price"], q=c["quantity"],
        )
    if publish:
        db.execute("UPDATE events SET status='published' WHERE id=:i", i=event_id)
    return {"ok": True, "event_id": event_id, "conversation_id": conv, "reason": ""}


def publish_event(system, event_id: int) -> dict:
    ev = system.db.one("SELECT * FROM events WHERE id=:i", i=event_id)
    if not ev or ev["status"] != "draft":
        return {"ok": False, "reason": "Only draft events can be published."}
    if parse(ev["start_time"]) <= clock.now():
        return {"ok": False, "reason": "This event's start time is in the past."}
    system.db.execute("UPDATE events SET status='published' WHERE id=:i AND status='draft'", i=event_id)
    return {"ok": True, "reason": ""}


def delete_draft(system, event_id: int) -> dict:
    ev = system.db.one("SELECT * FROM events WHERE id=:i", i=event_id)
    if not ev or ev["status"] != "draft":
        return {"ok": False, "reason": "Only draft events can be deleted."}
    system.bus.request(UI, "VenueAgent", "release_slot", kind="event", ref_id=event_id)
    system.db.execute("DELETE FROM ticket_categories WHERE event_id=:i", i=event_id)
    system.db.execute("DELETE FROM events WHERE id=:i", i=event_id)
    return {"ok": True, "reason": ""}


def cancel_event(system, event_id: int, reason: str = "") -> dict:
    return _answer(system.bus.request(UI, "BookingAgent", "cancel_event", event_id=event_id, reason=reason))


def book(system, user_id, event_id, items, simulate_failure=False) -> dict:
    return _answer(system.bus.request(
        UI, "BookingAgent", "book", user_id=user_id, event_id=event_id, items=items, simulate_failure=simulate_failure))


def cancel_booking(system, user_id, booking_id) -> dict:
    return _answer(system.bus.request(UI, "BookingAgent", "cancel", user_id=user_id, booking_id=booking_id))


def join_waitlist(system, user_id, event_id, category_id, quantity) -> dict:
    return _answer(system.bus.request(
        UI, "WaitlistAgent", "join", user_id=user_id, event_id=event_id, category_id=category_id, quantity=quantity))


def claim_offer(system, user_id, waitlist_id, simulate_failure=False) -> dict:
    return _answer(system.bus.request(
        UI, "WaitlistAgent", "claim", user_id=user_id, waitlist_id=waitlist_id, simulate_failure=simulate_failure))


def leave_waitlist(system, user_id, waitlist_id) -> dict:
    return _answer(system.bus.request(UI, "WaitlistAgent", "leave", user_id=user_id, waitlist_id=waitlist_id))


def request_hire(system, user_id, venue_id, start, end, guests, purpose) -> dict:
    reply = system.bus.request(UI, "VenueAgent", "hire_request", user_id=user_id, venue_id=venue_id,
                               start=start, end=end, guests=guests, purpose=purpose)
    out = _answer(reply)
    out["options"] = reply.content.get("options") or reply.content.get("suggestions", {}).get("alternative_venues", [])
    out["status"] = reply.content.get("status", "")
    return out


def decide_hire(system, admin_id, hire_id, approve, note="") -> dict:
    return _answer(system.bus.request(UI, "VenueAgent", "decide_hire", hire_id=hire_id, approve=approve,
                                      note=note, admin_id=admin_id))


def scan_ticket(system, staff_id, code, event_id) -> dict:
    reply = system.bus.request(UI, "TicketAgent", "scan", code=code, event_id=event_id, staff_id=staff_id)
    out = _answer(reply)
    out["result"] = reply.content.get("result", "unknown")
    return out
