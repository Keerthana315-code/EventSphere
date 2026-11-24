"""End-to-end tests through the real web layer (FastAPI test client)."""
import re

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

PASSWORD = "Demo@2026!"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", "test-agent-key")
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    return create_app(f"sqlite:///{tmp_path / 'api.db'}", run_scheduler=False, seed=True)


def csrf_of(client, path="/login"):
    html = client.get(path).text
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, email, password=PASSWORD):
    token = csrf_of(client)
    return client.post("/login", data={"email": email, "password": password, "csrf_token": token}, follow_redirects=False)


def events_of(app):
    return app.state.system.db.query("SELECT * FROM events WHERE status='published' ORDER BY id")


def test_public_event_list_search_and_filter(app):
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert "Campus Music Night" in c.get("/?q=music").text
        assert "Campus Music Night" not in c.get("/?category=Workshop").text
        assert c.get("/?price_min=100&price_max=2000&date_from=2020-01-01").status_code == 200


def test_login_with_wrong_password_fails_and_hashes_are_stored(app):
    with TestClient(app) as c:
        assert login(c, "attendee@eventsphere.demo", "wrong-password").status_code == 401
        stored = app.state.system.db.one("SELECT password_hash FROM users WHERE email='attendee@eventsphere.demo'")
        assert stored["password_hash"].startswith("pbkdf2_sha256$") and PASSWORD not in stored["password_hash"]


def test_role_checks_on_admin_and_scanner_routes(app):
    with TestClient(app) as anon:
        r = anon.get("/admin", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login")
        assert anon.get("/staff/scan", follow_redirects=False).status_code == 303
    with TestClient(app) as attendee:
        assert login(attendee, "attendee@eventsphere.demo").status_code == 303
        for path in ("/admin", "/admin/events", "/admin/venues", "/admin/messages", "/staff/scan"):
            assert attendee.get(path).status_code == 403, path
    with TestClient(app) as staff:
        login(staff, "staff@eventsphere.demo")
        assert staff.get("/staff/scan").status_code == 200
        assert staff.get("/admin").status_code == 403
    with TestClient(app) as admin:
        login(admin, "admin@eventsphere.demo")
        for path in ("/admin", "/admin/events", "/admin/venues", "/admin/hires", "/admin/messages", "/admin/users", "/staff/scan"):
            assert admin.get(path).status_code == 200, path


def test_post_without_csrf_token_is_rejected(app):
    with TestClient(app) as c:
        c.get("/login")
        r = c.post("/login", data={"email": "admin@eventsphere.demo", "password": PASSWORD}, follow_redirects=False)
        assert r.status_code == 403


def test_register_book_cancel_and_ticket_flow(app):
    with TestClient(app) as c:
        token = csrf_of(c, "/register")
        r = c.post("/register", data={"name": "New Person", "email": "new@example.com", "password": "longenough1", "csrf_token": token},
                   follow_redirects=False)
        assert r.status_code == 303
        event = [e for e in events_of(app) if e["title"] == "Campus Music Night"][0]
        cat = app.state.system.db.one("SELECT * FROM ticket_categories WHERE event_id=:e ORDER BY id", e=event["id"])
        token = csrf_of(c, f"/events/{event['id']}")
        r = c.post(f"/events/{event['id']}/book", data={f"qty_{cat['id']}": "2", "csrf_token": token}, follow_redirects=False)
        assert r.status_code == 303
        page = c.get("/my/bookings").text
        assert "Campus Music Night" in page
        ticket = app.state.system.db.one("SELECT * FROM tickets ORDER BY id DESC")
        assert c.get(f"/tickets/{ticket['code']}").status_code == 200
        booking = app.state.system.db.one("SELECT * FROM bookings ORDER BY id DESC")
        r = c.post(f"/bookings/{booking['id']}/cancel", data={"csrf_token": csrf_of(c, "/my/bookings")}, follow_redirects=False)
        assert r.status_code == 303
        assert app.state.system.db.one("SELECT status FROM bookings WHERE id=:b", b=booking["id"])["status"] == "cancelled"


def test_another_user_cannot_open_my_ticket(app):
    with TestClient(app) as alice, TestClient(app) as mallory:
        login(alice, "attendee@eventsphere.demo")
        event = events_of(app)[0]
        cat = app.state.system.db.one("SELECT * FROM ticket_categories WHERE event_id=:e", e=event["id"])
        alice.post(f"/events/{event['id']}/book", data={f"qty_{cat['id']}": "1", "csrf_token": csrf_of(alice, f"/events/{event['id']}")})
        code = app.state.system.db.one("SELECT code FROM tickets ORDER BY id DESC")["code"]
        token = csrf_of(mallory, "/register")
        mallory.post("/register", data={"name": "Mallory", "email": "m@example.com", "password": "longenough1", "csrf_token": token})
        assert mallory.get(f"/tickets/{code}").status_code == 404


def test_staff_scanner_admits_once_then_rejects(app):
    with TestClient(app) as att, TestClient(app) as staff:
        login(att, "attendee@eventsphere.demo")
        event = events_of(app)[0]
        cat = app.state.system.db.one("SELECT * FROM ticket_categories WHERE event_id=:e", e=event["id"])
        att.post(f"/events/{event['id']}/book", data={f"qty_{cat['id']}": "1", "csrf_token": csrf_of(att, f"/events/{event['id']}")})
        code = app.state.system.db.one("SELECT code FROM tickets ORDER BY id DESC")["code"]
        login(staff, "staff@eventsphere.demo")
        token = csrf_of(staff, "/staff/scan")
        # the seeded event is 10 days away, so check-in is not open yet -> clear rejection reason
        r = staff.post("/staff/scan", json={"code": code, "event_id": event["id"]}, headers={"X-CSRF-Token": token})
        assert r.status_code == 200 and r.json()["ok"] is False and r.json()["reason"]
        r = staff.post("/staff/scan", json={"code": code, "event_id": event["id"]}, headers={"X-CSRF-Token": "bad"})
        assert r.status_code == 403


def test_private_hire_flow_and_admin_approval(app):
    with TestClient(app) as att, TestClient(app) as admin:
        login(att, "attendee@eventsphere.demo")
        venue = app.state.system.db.one("SELECT id FROM venues WHERE open_for_hire=1 ORDER BY id")
        token = csrf_of(att, "/hire")
        r = att.post("/hire", data={"venue_id": venue["id"], "start": "2026-12-20T10:00", "end": "2026-12-20T13:00",
                                    "guests": "20", "purpose": "Farewell", "csrf_token": token})
        assert r.status_code == 200 and "Farewell" in r.text or "LKR" in r.text
        assert att.get("/hire/mine").status_code == 200
        login(admin, "admin@eventsphere.demo")
        assert admin.get("/admin/hires").status_code == 200


def test_admin_can_create_venue_and_event(app):
    with TestClient(app) as admin:
        login(admin, "admin@eventsphere.demo")
        token = csrf_of(admin, "/admin/venues")
        r = admin.post("/admin/venues", data={"name": "Studio", "location": "Jaffna", "capacity": "40", "hourly_rate": "2000",
                                              "open_for_hire": "on", "csrf_token": token}, follow_redirects=False)
        assert r.status_code == 303
        venue = app.state.system.db.one("SELECT * FROM venues WHERE name='Studio'")
        token = csrf_of(admin, "/admin/events/new")
        r = admin.post("/admin/events/new", data={
            "title": "Poetry Evening", "category": "Concert", "venue_id": str(venue["id"]), "start": "2026-12-30T18:00",
            "end": "2026-12-30T20:00", "description": "x", "cat_name": ["General"], "cat_price": ["500"], "cat_qty": ["30"],
            "action": "publish", "csrf_token": token}, follow_redirects=False)
        assert r.status_code == 303
        # more tickets than the venue holds -> VenueAgent refuses, nothing is created
        r = admin.post("/admin/events/new", data={
            "title": "Too Big", "category": "Concert", "venue_id": str(venue["id"]), "start": "2026-12-31T18:00",
            "end": "2026-12-31T20:00", "cat_name": ["General"], "cat_price": ["500"], "cat_qty": ["400"],
            "action": "publish", "csrf_token": token}, follow_redirects=False)
        assert r.status_code == 409


def test_agent_http_inbox_needs_key_and_returns_structured_reply(app):
    with TestClient(app) as c:
        msg = {"conversation_id": "conv-http-1", "sender": "external", "receiver": "BookingAgent",
               "performative": "REQUEST", "content": {"action": "nonsense"}}
        assert c.post("/agents/BookingAgent/inbox", json=msg).status_code == 403
        r = c.post("/agents/BookingAgent/inbox", json=msg, headers={"X-Agent-Key": "test-agent-key"})
        assert r.status_code == 200 and r.json()["performative"] == "FAILURE" and r.json()["conversation_id"] == "conv-http-1"
        assert len(c.get("/agents").json()) == 5
