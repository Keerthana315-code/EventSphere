"""Plain database queries used by the web layer (users, venues, events, dashboard).

Agents never use this module for decisions; they own their rules. This is read-mostly
glue for pages plus simple CRUD for users and venues.
"""
from . import clock
from .clock import fmt, parse
from .security import hash_password


# ------------------------------------------------------------------ users
def create_user(db, name: str, email: str, password: str, role: str = "attendee") -> int:
    return db.insert(
        "INSERT INTO users(name, email, password_hash, role, created_at) VALUES (:n, :e, :p, :r, :c)",
        n=name.strip(), e=email.strip().lower(), p=hash_password(password), r=role, c=fmt(clock.now()),
    )


def get_user(db, user_id: int):
    return db.one("SELECT id, name, email, role FROM users WHERE id=:i", i=user_id)


def get_user_by_email(db, email: str):
    return db.one("SELECT * FROM users WHERE email=:e", e=email.strip().lower())


# ----------------------------------------------------------------- venues
def list_venues(db):
    return db.query("SELECT * FROM venues ORDER BY name")


def get_venue(db, venue_id: int):
    return db.one("SELECT * FROM venues WHERE id=:i", i=venue_id)


def create_venue(db, d: dict) -> int:
    return db.insert(
        "INSERT INTO venues(name, location, capacity, description, image_url, hourly_rate, open_for_hire) "
        "VALUES (:name, :location, :capacity, :description, :image_url, :hourly_rate, :open_for_hire)",
        **{**d, "open_for_hire": int(d["open_for_hire"])},
    )


def update_venue(db, venue_id: int, d: dict) -> str | None:
    """Returns an error message, or None when saved."""
    biggest = db.scalar(
        "SELECT COALESCE(MAX(t.total), 0) FROM (SELECT SUM(c.quantity) AS total FROM ticket_categories c "
        "JOIN events e ON e.id=c.event_id WHERE e.venue_id=:v AND e.status <> 'cancelled' GROUP BY e.id) t", v=venue_id,
    )
    if d["capacity"] < biggest:
        return f"Capacity cannot be lower than {biggest}: an existing event already sells that many tickets here."
    db.execute(
        "UPDATE venues SET name=:name, location=:location, capacity=:capacity, description=:description, "
        "image_url=:image_url, hourly_rate=:hourly_rate, open_for_hire=:open_for_hire WHERE id=:id",
        **{**d, "open_for_hire": int(d["open_for_hire"]), "id": venue_id},
    )
    return None


# ----------------------------------------------------------------- events
def get_event(db, event_id: int):
    return db.one(
        "SELECT e.*, v.name AS venue_name, v.location AS venue_location, v.capacity AS venue_capacity "
        "FROM events e JOIN venues v ON v.id=e.venue_id WHERE e.id=:i", i=event_id,
    )


def event_categories(db, event_id: int):
    return db.query(
        "SELECT *, quantity - sold AS remaining FROM ticket_categories WHERE event_id=:e ORDER BY price, id", e=event_id
    )


def search_events(db, q="", category="", venue_id=None, date_from="", date_to="", price_min=None, price_max=None):
    where = ["e.status='published'", "e.end_time >= :now"]
    params = {"now": fmt(clock.now())}
    if q:
        where.append("(LOWER(e.title) LIKE :q OR LOWER(e.description) LIKE :q)")
        params["q"] = f"%{q.lower()}%"
    if category:
        where.append("e.category=:cat")
        params["cat"] = category
    if venue_id:
        where.append("e.venue_id=:vid")
        params["vid"] = venue_id
    if date_from:
        where.append("e.start_time >= :df")
        params["df"] = date_from + " 00:00:00"
    if date_to:
        where.append("e.start_time <= :dt")
        params["dt"] = date_to + " 23:59:59"
    if price_min is not None:
        where.append("(SELECT MIN(price) FROM ticket_categories c WHERE c.event_id=e.id) >= :pmin")
        params["pmin"] = price_min
    if price_max is not None:
        where.append("(SELECT MIN(price) FROM ticket_categories c WHERE c.event_id=e.id) <= :pmax")
        params["pmax"] = price_max
    return db.query(
        "SELECT e.*, v.name AS venue_name, "
        "(SELECT MIN(price) FROM ticket_categories c WHERE c.event_id=e.id) AS min_price, "
        "(SELECT COALESCE(SUM(quantity - sold), 0) FROM ticket_categories c WHERE c.event_id=e.id) AS left_total "
        "FROM events e JOIN venues v ON v.id=e.venue_id WHERE " + " AND ".join(where) + " ORDER BY e.start_time",
        **params,
    )


def admin_events(db):
    return db.query(
        "SELECT e.*, v.name AS venue_name, "
        "(SELECT COALESCE(SUM(quantity), 0) FROM ticket_categories c WHERE c.event_id=e.id) AS total_tickets, "
        "(SELECT COALESCE(SUM(sold), 0) FROM ticket_categories c WHERE c.event_id=e.id) AS sold "
        "FROM events e JOIN venues v ON v.id=e.venue_id ORDER BY e.start_time DESC"
    )


# ------------------------------------------------------- user-facing lists
def user_bookings(db, user_id: int):
    bookings = db.query(
        "SELECT b.*, e.title, e.start_time, e.status AS event_status FROM bookings b JOIN events e ON e.id=b.event_id "
        "WHERE b.user_id=:u AND b.status IN ('confirmed','cancelled') ORDER BY b.id DESC", u=user_id,
    )
    for b in bookings:
        b["tickets"] = db.query(
            "SELECT t.*, k.name AS category_name FROM tickets t JOIN ticket_categories k ON k.id=t.category_id "
            "WHERE t.booking_id=:b ORDER BY t.id", b=b["id"],
        )
    return bookings


def user_waitlist(db, user_id: int):
    rows = db.query(
        "SELECT w.*, e.title, k.name AS category_name FROM waitlist w JOIN events e ON e.id=w.event_id "
        "JOIN ticket_categories k ON k.id=w.category_id WHERE w.user_id=:u AND w.status IN ('waiting','offered') ORDER BY w.id DESC",
        u=user_id,
    )
    now = clock.now()
    for r in rows:
        r["seconds_left"] = max(0, int((parse(r["expires_at"]) - now).total_seconds())) if r["expires_at"] else None
    return rows


def user_hires(db, user_id: int):
    return db.query(
        "SELECT h.*, v.name AS venue_name FROM hire_requests h JOIN venues v ON v.id=h.venue_id WHERE h.user_id=:u ORDER BY h.id DESC",
        u=user_id,
    )


def unread_count(db, user_id: int) -> int:
    return db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id=:u AND is_read=0", u=user_id) or 0


# -------------------------------------------------------------- dashboard
def dashboard(db):
    events = db.query(
        "SELECT e.id, e.title, e.status, e.start_time, v.capacity AS venue_capacity, "
        "(SELECT COALESCE(SUM(quantity), 0) FROM ticket_categories c WHERE c.event_id=e.id) AS ticket_capacity, "
        "(SELECT COALESCE(SUM(sold), 0) FROM ticket_categories c WHERE c.event_id=e.id) AS sold, "
        "(SELECT COALESCE(SUM(total - refund_amount), 0) FROM bookings b WHERE b.event_id=e.id AND b.status IN ('confirmed','cancelled')) AS revenue, "
        "(SELECT COUNT(*) FROM tickets t WHERE t.event_id=e.id AND t.status='used') AS checkins "
        "FROM events e JOIN venues v ON v.id=e.venue_id WHERE e.status <> 'draft' ORDER BY e.start_time"
    )
    by_hour: dict[str, int] = {}
    for row in db.query("SELECT used_at FROM tickets WHERE used_at IS NOT NULL ORDER BY used_at"):
        key = row["used_at"][:13] + ":00"
        by_hour[key] = by_hour.get(key, 0) + 1
    totals = {
        "sold": sum(e["sold"] for e in events),
        "revenue": round(sum(e["revenue"] for e in events), 2),
        "checkins": sum(e["checkins"] for e in events),
    }
    suspicious = [
        {"code": r["state_key"][5:11] + "...", **__import__("json").loads(r["state_value"])}
        for r in db.query("SELECT state_key, state_value FROM agent_state WHERE agent='TicketAgent' AND state_key LIKE 'scan:%'")
        if __import__("json").loads(r["state_value"]).get("flagged")
    ]
    return {"events": events, "totals": totals, "checkins_by_hour": by_hour, "suspicious": suspicious}


def agent_states(db):
    return db.query("SELECT agent, state_key, state_value FROM agent_state WHERE state_key NOT LIKE 'scan:%' ORDER BY agent, state_key")
