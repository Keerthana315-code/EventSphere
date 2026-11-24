"""WaitlistAgent: join rules, timed holds, expiry sweep and re-offer."""
from datetime import datetime

from app import clock, repo, services


def sold_out_event(world, quantity=1):
    event = world.make_event(quantity=quantity)["event_id"]
    assert world.book(world.alice, event, quantity)["ok"]
    return event


def join(world, user, event, qty=1):
    cat = world.category(event)
    return services.join_waitlist(world.system, user, event, cat["id"], qty)


def entry(world, user):
    return world.db.one("SELECT * FROM waitlist WHERE user_id=:u ORDER BY id DESC", u=user)


def test_cannot_join_while_seats_are_available(world):
    event = world.make_event(quantity=5)["event_id"]
    result = join(world, world.bob, event)
    assert not result["ok"] and "book directly" in result["reason"]


def test_join_when_sold_out_and_no_duplicates(world):
    event = sold_out_event(world)
    first = join(world, world.bob, event)
    assert first["ok"] and first["content"]["position"] == 1
    assert not join(world, world.bob, event)["ok"]


def test_cancellation_offers_seat_to_first_in_line_and_holds_it(world):
    event = sold_out_event(world)
    carol = repo.create_user(world.db, "Carol", "carol@t.io", "password1")
    join(world, world.bob, event)
    join(world, carol, event)
    booking = world.db.one("SELECT id FROM bookings")["id"]
    services.cancel_booking(world.system, world.alice, booking)
    assert entry(world, world.bob)["status"] == "offered"      # first come, first served
    assert entry(world, carol)["status"] == "waiting"
    assert world.category(event)["sold"] == 1                  # the seat is HELD, nobody else can buy it
    assert not world.book(world.alice, event)["ok"]
    assert world.db.scalar("SELECT COUNT(*) FROM notifications WHERE title LIKE 'Seats available%'") == 1


def test_claiming_an_offer_books_the_held_seat(world):
    event = sold_out_event(world)
    join(world, world.bob, event)
    services.cancel_booking(world.system, world.alice, world.db.one("SELECT id FROM bookings")["id"])
    result = services.claim_offer(world.system, world.bob, entry(world, world.bob)["id"])
    assert result["ok"] and entry(world, world.bob)["status"] == "claimed"
    assert world.category(event)["sold"] == 1               # still exactly one seat sold, not two
    assert world.db.scalar("SELECT COUNT(*) FROM tickets WHERE user_id=:u AND status='valid'", u=world.bob) == 1


def test_timer_sweep_expires_unclaimed_hold_and_reoffers(world):
    event = sold_out_event(world)
    carol = repo.create_user(world.db, "Carol", "carol@t.io", "password1")
    join(world, world.bob, event)
    join(world, carol, event)
    services.cancel_booking(world.system, world.alice, world.db.one("SELECT id FROM bookings")["id"])
    # nothing happens before the 10-minute hold runs out
    assert world.system.sweep().content["expired"] == 0
    clock.set_now(datetime(2026, 11, 14, 12, 11))
    swept = world.system.sweep()
    assert swept.content == {"expired": 1, "reoffered": 1}
    assert entry(world, world.bob)["status"] == "expired" and entry(world, carol)["status"] == "offered"
    assert world.category(event)["sold"] == 1
    late = services.claim_offer(world.system, world.bob, entry(world, world.bob)["id"])
    assert not late["ok"]


def test_expired_hold_cannot_be_claimed_even_before_the_sweep_runs(world):
    event = sold_out_event(world)
    join(world, world.bob, event)
    services.cancel_booking(world.system, world.alice, world.db.one("SELECT id FROM bookings")["id"])
    clock.set_now(datetime(2026, 11, 14, 12, 30))
    assert "expired" in services.claim_offer(world.system, world.bob, entry(world, world.bob)["id"])["reason"]


def test_event_cancellation_clears_the_waitlist(world):
    event = sold_out_event(world)
    join(world, world.bob, event)
    services.cancel_event(world.system, event, "Storm")
    assert entry(world, world.bob)["status"] == "cancelled"
    assert world.db.scalar("SELECT COUNT(*) FROM notifications WHERE title='Waitlist closed'") == 1
