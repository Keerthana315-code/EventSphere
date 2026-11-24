"""VenueAgent: calendar clashes, capacity, private-hire decisions and pricing."""
from app import repo, services
from app.agents.venue_agent import price_hire
from app.bus import Performative
from app.clock import parse


def hire(world, start, end, guests=10, venue=None):
    return world.system.bus.request(
        "test", "VenueAgent", "hire_request", user_id=world.alice, venue_id=venue or world.venue,
        start=start, end=end, guests=guests, purpose="Farewell")


def test_event_overlap_refused_with_reason_and_alternatives(world):
    assert world.make_event()["ok"]
    clash = world.make_event(start="2026-11-25 19:00:00", end="2026-11-25 21:00:00", title="Clash")
    assert not clash["ok"]
    assert "clashes with" in clash["reason"] and "Test Event" in clash["reason"]
    assert clash["suggestions"]["alternative_times"], "a refusal must come with usable alternatives"


def test_turnaround_buffer_is_enforced(world):
    assert world.make_event()["ok"]  # 18:00-20:00
    too_close = world.make_event(start="2026-11-25 20:15:00", end="2026-11-25 21:00:00")
    assert not too_close["ok"] and "30-minute" in too_close["reason"]
    ok = world.make_event(start="2026-11-25 20:30:00", end="2026-11-25 21:30:00")
    assert ok["ok"]


def test_tickets_may_not_exceed_venue_capacity(world):
    result = world.make_event(quantity=101)
    assert not result["ok"] and "capacity" in result["reason"]
    assert world.db.scalar("SELECT COUNT(*) FROM events") == 0  # nothing half-created


def test_routine_hire_is_confirmed_with_weekend_price(world):
    # Saturday 14:00-16:00 at 1000/h: 2 h x 1000 x 1.25
    reply = hire(world, "2026-11-21 14:00:00", "2026-11-21 16:00:00")
    assert reply.performative == Performative.AGREE
    assert reply.content["status"] == "confirmed" and reply.content["quote"]["total"] == 2500.0


def test_large_group_is_escalated_then_admin_approves(world):
    reply = hire(world, "2026-11-19 10:00:00", "2026-11-19 12:00:00", guests=90)  # 90 % of capacity
    assert reply.performative == Performative.INFORM and reply.content["status"] == "escalated"
    decision = services.decide_hire(world.system, world.admin, reply.content["hire_id"], True)
    assert decision["ok"]
    assert world.db.one("SELECT status FROM hire_requests WHERE id=:i", i=reply.content["hire_id"])["status"] == "confirmed"
    # a second decision is refused
    assert not services.decide_hire(world.system, world.admin, reply.content["hire_id"], False)["ok"]


def test_hire_clash_gets_proposal_instead_of_plain_refusal(world):
    assert hire(world, "2026-11-19 10:00:00", "2026-11-19 12:00:00").performative == Performative.AGREE
    other = repo.create_venue(world.db, dict(name="Room B", location="x", capacity=50, hourly_rate=500,
                                             description="", image_url="", open_for_hire=True))
    reply = hire(world, "2026-11-19 11:00:00", "2026-11-19 13:00:00")
    assert reply.performative == Performative.PROPOSE
    assert reply.content["reason"] and reply.content["options"]
    assert any(o["venue_id"] == other for o in reply.content["options"])  # another venue at the same time
    assert any(o["venue_id"] == world.venue for o in reply.content["options"])  # another time here


def test_hire_rules_refuse_with_reason(world):
    assert "notice" in hire(world, "2026-11-14 13:00:00", "2026-11-14 15:00:00").content["reason"]
    assert "between" in hire(world, "2026-11-20 08:00:00", "2026-11-20 23:00:00").content["reason"]
    closed = repo.create_venue(world.db, dict(name="Closed", location="x", capacity=50, hourly_rate=1,
                                              description="", image_url="", open_for_hire=False))
    assert "not open for private hire" in hire(world, "2026-11-20 10:00:00", "2026-11-20 12:00:00", venue=closed).content["reason"]


def test_price_has_evening_surcharge():
    assert price_hire(1000, parse("2026-11-18 19:00:00"), parse("2026-11-18 21:00:00"))["total"] == 2200.0
