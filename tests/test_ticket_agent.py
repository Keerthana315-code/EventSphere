"""TicketAgent: every ticket is admitted exactly once."""
from datetime import datetime

from app import clock, services


def setup_ticket(world):
    event = world.make_event(quantity=5)["event_id"]
    world.book(world.alice, event)
    code = world.db.one("SELECT code FROM tickets WHERE event_id=:e", e=event)["code"]
    clock.set_now(datetime(2026, 11, 25, 17, 0))  # doors are open (2 h before 18:00)
    return event, code


def scan(world, code, event):
    return services.scan_ticket(world.system, world.staff, code, event)


def test_codes_are_unique_and_unguessable(world):
    event = world.make_event(quantity=6)["event_id"]
    world.book(world.alice, event, 6)
    codes = [r["code"] for r in world.db.query("SELECT code FROM tickets")]
    assert len(set(codes)) == 6 and all(len(c) >= 20 for c in codes)


def test_valid_ticket_is_admitted_once_only(world):
    event, code = setup_ticket(world)
    first = scan(world, code, event)
    assert first["ok"] and first["result"] == "admit"
    second = scan(world, code, event)  # double check-in
    assert not second["ok"] and second["result"] == "already_used" and "Already used" in second["reason"]


def test_ticket_for_another_event_is_rejected(world):
    event, code = setup_ticket(world)
    clock.set_now(datetime(2026, 11, 14, 12))
    other = world.make_event(start="2026-11-28 18:00:00", end="2026-11-28 20:00:00", title="Other")["event_id"]
    clock.set_now(datetime(2026, 11, 25, 17, 0))
    wrong = scan(world, code, other)
    assert wrong["result"] == "wrong_event" and "Test Event" in wrong["reason"]
    assert scan(world, code, event)["result"] == "admit"  # a wrong-event scan does not burn the ticket


def test_cancelled_ticket_and_unknown_code_are_rejected(world):
    event, code = setup_ticket(world)
    booking = world.db.one("SELECT id FROM bookings")["id"]
    clock.set_now(datetime(2026, 11, 14, 12))
    services.cancel_booking(world.system, world.alice, booking)
    clock.set_now(datetime(2026, 11, 25, 17, 0))
    assert scan(world, code, event)["result"] == "cancelled"
    assert scan(world, "not-a-real-code", event)["result"] == "unknown"


def test_check_in_only_inside_the_time_window(world):
    event = world.make_event()["event_id"]
    world.book(world.alice, event)
    code = world.db.one("SELECT code FROM tickets")["code"]
    clock.set_now(datetime(2026, 11, 25, 10, 0))
    early = scan(world, code, event)
    assert early["result"] == "outside_window" and "not open yet" in early["reason"]
    clock.set_now(datetime(2026, 11, 25, 21, 0))
    assert scan(world, code, event)["result"] == "outside_window"


def test_repeated_scans_are_flagged_as_suspicious_and_survive_restart(world):
    event, code = setup_ticket(world)
    scan(world, code, event)
    scan(world, code, event)
    third = scan(world, code, event)  # 2 rejected re-scans -> flagged
    assert third["content"]["suspicious"]
    assert world.db.scalar("SELECT COUNT(*) FROM notifications WHERE title='Suspicious ticket scans'") == 1
    # beliefs live in the database, so a brand-new agent object (a "restart") still knows
    from app.agents.ticket_agent import TicketAgent
    fresh = TicketAgent(world.db, world.system.bus)
    assert fresh.get_state("scan:" + code)["flagged"] is True
