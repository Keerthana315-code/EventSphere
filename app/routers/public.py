from fastapi import APIRouter, Depends, HTTPException, Request

from .. import clock, repo, rules
from ..clock import parse
from ..web import current_user, get_system, render, to_number

router = APIRouter()


@router.get("/")
def event_list(request: Request, q: str = "", category: str = "", venue_id: str = "", date_from: str = "",
               date_to: str = "", price_min: str = "", price_max: str = ""):
    db = get_system(request).db
    events = repo.search_events(
        db, q=q.strip(), category=category, venue_id=to_number(venue_id, int), date_from=date_from, date_to=date_to,
        price_min=to_number(price_min), price_max=to_number(price_max),
    )
    filters = dict(q=q, category=category, venue_id=venue_id, date_from=date_from, date_to=date_to,
                   price_min=price_min, price_max=price_max)
    return render(request, "events.html", events=events, venues=repo.list_venues(db), categories=rules.EVENT_CATEGORIES, f=filters)


@router.get("/events/{event_id}")
def event_page(request: Request, event_id: int):
    db = get_system(request).db
    event = repo.get_event(db, event_id)
    user = current_user(request)
    if not event or (event["status"] == "draft" and not (user and user["role"] == "admin")):
        raise HTTPException(status_code=404, detail="Event not found.")
    waiting = []
    if user:
        waiting = db.query("SELECT * FROM waitlist WHERE user_id=:u AND event_id=:e AND status IN ('waiting','offered')",
                           u=user["id"], e=event_id)
    return render(
        request, "event.html", event=event, categories=repo.event_categories(db, event_id),
        started=parse(event["start_time"]) <= clock.now(), waiting={w["category_id"]: w for w in waiting},
        max_qty=rules.MAX_TICKETS_PER_REQUEST, policy=rules.REFUND_POLICY_TEXT,
    )
