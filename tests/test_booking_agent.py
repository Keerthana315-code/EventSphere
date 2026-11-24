"""BookingAgent: overbooking protection, limits, refunds and event cancellation."""
import threading
from datetime import datetime

from app import clock, repo, services
from app.bus import Performative


def test_never_sells_more_than_exists(world):
    event = world.make_event(quantity=2)["event_id"]
    assert world.book(world.alice, event, 2)["ok"]
    refused = world.book(world.bob, event, 1)
    assert not refused["ok"] and refused["content"]["waitlist_available"] and "left" in refused["reason"]
    assert world.category(event)["sold"] == 2


def test_two_people_racing_for_the_last_seats_cannot_oversell(world):
    event = world.make_event(quantity=5)["event_id"]
    users = [repo.create_user(world.db, f"U{i}", f"u{i}@t.io", "password1") for i in range(20)]
    results = []

    def go(user):
        results.append(world.book(user, event, 1)["ok"])

    threads = [threading.Thread(target=go, args=(u,)) for u in users]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(True) == 5 and results.count(False) == 15
    assert world.category(event)["sold"] == 5
    assert world.db.scalar("SELECT COUNT(*) FROM tickets WHERE event_id=:e", e=event) == 5


def test_quantity_limits(world):
    event = world.make_event(quantity=50)["event_id"]
    too_many = world.book(world.alice, event, 7)
    assert not too_many["ok"] and "at most 6" in too_many["reason"]
    assert world.book(world.alice, event, 6)["ok"]
    assert world.book(world.alice, event, 4)["ok"]  # 10 in total is the cap
    capped = world.book(world.alice, event, 1)
    assert not capped["ok"] and "per person" in capped["reason"]


def test_cannot_book_draft_or_started_event(world):
    draft = world.make_event(publish=False)["event_id"]
    assert not world.book(world.alice, draft)["ok"]
    event = world.make_event(start="2026-11-26 10:00:00", end="2026-11-26 12:00:00", title="Later")["event_id"]
    clock.set_now(datetime(2026, 11, 26, 10, 30))
    assert "started" in world.book(world.alice, event)["reason"]


def test_simulated_payment_records_reference_and_failure_rolls_back(world):
    event = world.make_event(quantity=3)["event_id"]
    ok = world.book(world.alice, event, 1)
    assert ok["content"]["payment_ref"].startswith("SIM-")
    failed = world.book(world.bob, event, 2, simulate_failure=True)
    assert failed["performative"] == "FAILURE"
    assert world.category(event)["sold"] == 1  # seats of the failed payment were released


def test_refund_policy_tiers(world):
    event = world.make_event(quantity=10, price=1000)["event_id"]  # starts 2026-11-25 18:00
    cases = [(datetime(2026, 11, 14, 12), 100), (datetime(2026, 11, 22, 12), 50), (datetime(2026, 11, 24, 12), 0)]
    for moment, expected in cases:
        clock.set_now(datetime(2026, 11, 14, 12))
        booking = world.book(world.alice, event, 2)["content"]["booking_id"]
        clock.set_now(moment)
        result = services.cancel_booking(world.system, world.alice, booking)
        assert result["ok"] and result["content"]["percent"] == expected
        assert result["content"]["refund"] == 2000 * expected / 100
    assert world.category(event)["sold"] == 0  # every cancelled seat went back on sale


def test_cancelling_twice_or_someone_elses_booking_is_refused(world):
    event = world.make_event()["event_id"]
    booking = world.book(world.alice, event)["content"]["booking_id"]
    assert not services.cancel_booking(world.system, world.bob, booking)["ok"]
    assert services.cancel_booking(world.system, world.alice, booking)["ok"]
    assert not services.cancel_booking(world.system, world.alice, booking)["ok"]


def test_organiser_cancelling_refunds_everyone_fully_and_frees_the_venue(world):
    event = world.make_event(quantity=10, price=500)["event_id"]
    world.book(world.alice, event, 2)
    world.book(world.bob, event, 1)
    clock.set_now(datetime(2026, 11, 24, 12))  # normally 0 % refund this late
    result = services.cancel_event(world.system, event, "Storm")
    assert result["ok"] and result["content"]["refunded_total"] == 1500
    assert world.db.scalar("SELECT COUNT(*) FROM tickets WHERE event_id=:e AND status='valid'", e=event) == 0
    clock.set_now(datetime(2026, 11, 14, 12))
    assert world.make_event(title="Replacement")["ok"]  # VenueAgent released the slot
    assert world.db.scalar("SELECT COUNT(*) FROM notifications WHERE title='Event cancelled'") == 2


def test_booking_agent_refuses_unknown_actions(world):
    reply = world.system.bus.request("test", "BookingAgent", "make_coffee")
    assert reply.performative == Performative.FAILURE
