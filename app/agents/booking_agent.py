"""BookingAgent - goal: sell tickets fairly without ever overselling.

Decision rules:
  B1  refuse unless the event is published and has not started
  B2  refuse more than 6 tickets in one booking, and more than 10 per person per event
  B3  refuse a category that does not belong to the event
  B4  refuse (with the number left and a waitlist hint) when a category cannot cover the request.
      Seat counting is ONE atomic SQL statement:
          UPDATE ticket_categories SET sold = sold + :q WHERE id = :id AND sold + :q <= quantity
      so two people booking the last seat at the same moment cannot both succeed.
      A CHECK constraint in the database is a second safety net.
  B5  payment is simulated; a payment reference is recorded; FAILURE if the (simulated) payment fails
  B6  refund on cancellation: 100 % >= 7 days before start, 50 % >= 48 h, otherwise 0 %
  B7  if the organiser cancels an event, EVERY confirmed booking is refunded 100 %
"""
import secrets
from datetime import timedelta  # noqa: F401  (kept for readability of rules)

from .. import clock, rules
from ..bus import Performative
from ..clock import fmt, parse
from .base import Agent


class BookingAgent(Agent):
    name = "BookingAgent"
    goal = "Sell tickets fairly without overselling"

    # ------------------------------------------------------------ helpers
    def _release(self, reserved):
        for category_id, qty in reserved:
            self.db.execute(
                "UPDATE ticket_categories SET sold = sold - :q WHERE id=:i AND sold >= :q", q=qty, i=category_id
            )

    def _reserve(self, category_id, qty) -> bool:
        return self.db.execute(
            "UPDATE ticket_categories SET sold = sold + :q WHERE id=:i AND sold + :q <= quantity",
            q=qty, i=category_id,
        ) == 1

    # ------------------------------------------------------- availability
    def on_availability(self, msg):
        category = self.db.one(
            "SELECT c.*, e.status AS event_status, e.start_time AS event_start FROM ticket_categories c "
            "JOIN events e ON e.id = c.event_id WHERE c.id=:i", i=int(msg.content["category_id"]),
        )
        if not category:
            return self.refuse(msg, "Unknown ticket category.")
        return self.inform(
            msg, category_id=category["id"], event_id=category["event_id"], name=category["name"],
            remaining=category["quantity"] - category["sold"], event_status=category["event_status"],
            event_started=parse(category["event_start"]) <= clock.now(),
        )

    # ------------------------------------------------------------- booking
    def on_book(self, msg):
        c, conv = msg.content, msg.conversation_id
        try:
            user_id, event_id = int(c["user_id"]), int(c["event_id"])
            wanted: dict[int, int] = {}
            for item in c["items"]:
                qty = int(item["qty"])
                if qty > 0:
                    wanted[int(item["category_id"])] = wanted.get(int(item["category_id"]), 0) + qty
        except (KeyError, ValueError, TypeError):
            return self.refuse(msg, "Invalid booking request.")
        held = bool(c.get("held"))  # seats already reserved for this person by the WaitlistAgent
        if not wanted:
            return self.refuse(msg, "Choose at least one ticket.")
        total_qty = sum(wanted.values())

        event = self.db.one("SELECT * FROM events WHERE id=:i", i=event_id)
        if not event or event["status"] != "published":                                        # B1
            return self.refuse(msg, "This event is not open for booking.")
        if parse(event["start_time"]) <= clock.now():
            return self.refuse(msg, "Sales are closed: the event has already started.")
        if total_qty > rules.MAX_TICKETS_PER_REQUEST:                                          # B2
            self.incr("refused_quantity")
            return self.refuse(msg, f"You can book at most {rules.MAX_TICKETS_PER_REQUEST} tickets at a time (you asked for {total_qty}).")
        existing = self.db.scalar(
            "SELECT COUNT(*) FROM tickets WHERE user_id=:u AND event_id=:e AND status <> 'cancelled'", u=user_id, e=event_id
        )
        if existing + total_qty > rules.MAX_TICKETS_PER_USER_PER_EVENT:
            self.incr("refused_quantity")
            return self.refuse(msg, f"Limit of {rules.MAX_TICKETS_PER_USER_PER_EVENT} tickets per person for this event (you already hold {existing}).")

        categories = {}
        for category_id in wanted:
            row = self.db.one("SELECT * FROM ticket_categories WHERE id=:i AND event_id=:e", i=category_id, e=event_id)
            if not row:                                                                        # B3
                return self.refuse(msg, "Unknown ticket category for this event.")
            categories[category_id] = row

        reserved = []
        if not held:
            for category_id, qty in wanted.items():                                            # B4
                if self._reserve(category_id, qty):
                    reserved.append((category_id, qty))
                    continue
                self._release(reserved)
                fresh = self.db.one("SELECT quantity - sold AS left FROM ticket_categories WHERE id=:i", i=category_id)["left"]
                self.incr("refused_sold_out")
                return self.refuse(
                    msg, f"Only {fresh} '{categories[category_id]['name']}' ticket(s) left - you asked for {qty}.",
                    category_id=category_id, remaining=fresh, waitlist_available=True,
                )

        total = round(sum(categories[i]["price"] * q for i, q in wanted.items()), 2)
        booking_id = self.db.insert(
            "INSERT INTO bookings(user_id, event_id, status, total, created_at) VALUES (:u, :e, 'pending', :t, :c)",
            u=user_id, e=event_id, t=total, c=fmt(clock.now()),
        )

        if c.get("simulate_failure"):                                                          # B5
            self._release(reserved)
            self.db.execute("UPDATE bookings SET status='failed', cancel_reason='payment declined' WHERE id=:i", i=booking_id)
            return self.failure(msg, "The simulated payment was declined. No money was taken and your seats were released.")
        payment_ref = "SIM-" + secrets.token_hex(5).upper()
        self.db.execute("UPDATE bookings SET payment_ref=:p WHERE id=:i", p=payment_ref, i=booking_id)

        issued = self.ask(
            "TicketAgent", "issue_tickets", conv, booking_id=booking_id, event_id=event_id, user_id=user_id,
            items=[{"category_id": i, "qty": q, "price": categories[i]["price"]} for i, q in wanted.items()],
        )
        if issued.performative != Performative.INFORM:
            self._release(reserved)
            self.db.execute("UPDATE bookings SET status='failed', cancel_reason='ticket issue failed' WHERE id=:i", i=booking_id)
            return self.failure(msg, "Tickets could not be issued, so the booking was rolled back.")

        self.db.execute("UPDATE bookings SET status='confirmed' WHERE id=:i", i=booking_id)
        self.incr("tickets_sold", total_qty)
        self.announce("booking_confirmed", conv, booking_id=booking_id, user_id=user_id, event_id=event_id,
                      event_title=event["title"], count=total_qty, total=total, payment_ref=payment_ref)
        return self.agree(msg, booking_id=booking_id, payment_ref=payment_ref, total=total, count=total_qty)

    # ----------------------------------------------------------- cancelling
    def on_cancel(self, msg):
        c, conv = msg.content, msg.conversation_id
        booking = self.db.one("SELECT * FROM bookings WHERE id=:i", i=int(c["booking_id"]))
        if not booking or booking["user_id"] != int(c["user_id"]):
            return self.refuse(msg, "Booking not found.")
        if booking["status"] != "confirmed":
            return self.refuse(msg, f"This booking is already {booking['status']}.")
        event = self.db.one("SELECT * FROM events WHERE id=:i", i=booking["event_id"])
        start, now = parse(event["start_time"]), clock.now()
        if now >= start:
            return self.refuse(msg, "The event has started, so cancellation is closed.")
        used = self.db.scalar("SELECT COUNT(*) FROM tickets WHERE booking_id=:b AND status='used'", b=booking["id"])
        if used:
            return self.refuse(msg, "Some tickets were already used at the gate, so this booking cannot be cancelled.")

        percent = rules.refund_percent((start - now).total_seconds() / 3600)                   # B6
        refund = round(booking["total"] * percent / 100, 2)
        changed = self.db.execute(
            "UPDATE bookings SET status='cancelled', refund_amount=:r, refund_percent=:p, cancelled_at=:n, "
            "cancel_reason='customer' WHERE id=:i AND status='confirmed'",
            r=refund, p=percent, n=fmt(now), i=booking["id"],
        )
        if changed != 1:  # someone cancelled in the same instant
            return self.refuse(msg, "This booking is already cancelled.")
        freed = self.db.query(
            "SELECT category_id, COUNT(*) AS n FROM tickets WHERE booking_id=:b AND status='valid' GROUP BY category_id",
            b=booking["id"],
        )
        self.ask("TicketAgent", "cancel_tickets", conv, booking_id=booking["id"])
        self._release([(f["category_id"], f["n"]) for f in freed])
        self.announce("booking_cancelled", conv, booking_id=booking["id"], user_id=booking["user_id"],
                      event_id=event["id"], event_title=event["title"], refund=refund, percent=percent)
        for f in freed:  # tell everyone interested (the WaitlistAgent reacts) that seats are free
            self.announce("seats_freed", conv, event_id=event["id"], category_id=f["category_id"], qty=f["n"])
        return self.agree(msg, refund=refund, percent=percent)

    def on_cancel_event(self, msg):
        c, conv = msg.content, msg.conversation_id
        event = self.db.one("SELECT * FROM events WHERE id=:i", i=int(c["event_id"]))
        if not event:
            return self.refuse(msg, "Event not found.")
        if event["status"] == "cancelled":
            return self.refuse(msg, "Event is already cancelled.")
        reason = str(c.get("reason", "")).strip() or "Cancelled by the organiser"
        self.db.execute("UPDATE events SET status='cancelled', cancel_reason=:r WHERE id=:i", r=reason, i=event["id"])
        refunds = []
        for b in self.db.query("SELECT * FROM bookings WHERE event_id=:e AND status='confirmed'", e=event["id"]):  # B7
            self.db.execute(
                "UPDATE bookings SET status='cancelled', refund_amount=total, refund_percent=100, cancelled_at=:n, "
                "cancel_reason='event cancelled' WHERE id=:i", n=fmt(clock.now()), i=b["id"],
            )
            self.ask("TicketAgent", "cancel_tickets", conv, booking_id=b["id"])
            refunds.append({"booking_id": b["id"], "user_id": b["user_id"], "amount": b["total"]})
        self.incr("events_cancelled")
        self.announce("event_cancelled", conv, event_id=event["id"], event_title=event["title"], reason=reason, refunds=refunds)
        return self.agree(msg, refunded_bookings=len(refunds), refunded_total=round(sum(r["amount"] for r in refunds), 2))

    # --------------------------------------------------- holds (for waitlist)
    def on_hold_seats(self, msg):
        category_id, qty = int(msg.content["category_id"]), int(msg.content["qty"])
        category = self.db.one(
            "SELECT c.*, e.status AS event_status FROM ticket_categories c JOIN events e ON e.id=c.event_id WHERE c.id=:i",
            i=category_id,
        )
        if not category or category["event_status"] != "published":
            return self.refuse(msg, "Event is not open for booking.")
        if not self._reserve(category_id, qty):
            return self.refuse(msg, "Not enough seats free to hold.")
        return self.agree(msg, category_id=category_id, qty=qty)

    def on_release_hold(self, msg):
        self._release([(int(msg.content["category_id"]), int(msg.content["qty"]))])
        return self.inform(msg, released=True)
