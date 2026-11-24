"""WaitlistAgent - goal: pass freed seats to waiting customers.

Decision rules:
  W1  a person may join only when the category cannot cover the quantity they want
      (otherwise REFUSE "book directly"); 1-6 tickets; one active entry per category
  W2  freed seats are offered first-come-first-served; if the first person needs more seats than
      are free, the next person who fits gets them (the first keeps their place)
  W3  an offer HOLDS the seats (via BookingAgent) for WAITLIST_HOLD_MINUTES (default 10)
  W4  an unclaimed hold expires on a timer (``sweep``), the seats are released and re-offered
  W5  reactive: listens for the broadcast INFORM ``seats_freed`` and ``event_cancelled``
"""
from datetime import timedelta

from .. import clock, rules
from ..bus import Performative
from ..clock import fmt, parse
from ..config import get_settings
from .base import Agent


class WaitlistAgent(Agent):
    name = "WaitlistAgent"
    goal = "Pass freed seats to waiting customers"

    def __init__(self, db, bus, hold_minutes: int | None = None):
        super().__init__(db, bus)
        self.hold_minutes = hold_minutes if hold_minutes is not None else get_settings().hold_minutes

    # ----------------------------------------------------------------- join
    def on_join(self, msg):
        c = msg.content
        try:
            user_id, event_id, category_id, qty = int(c["user_id"]), int(c["event_id"]), int(c["category_id"]), int(c["quantity"])
        except (KeyError, ValueError, TypeError):
            return self.refuse(msg, "Invalid waitlist request.")
        if not 1 <= qty <= rules.MAX_TICKETS_PER_REQUEST:
            return self.refuse(msg, f"You can wait for 1 to {rules.MAX_TICKETS_PER_REQUEST} tickets.")
        av = self.ask("BookingAgent", "availability", msg.conversation_id, category_id=category_id)
        if av.performative != Performative.INFORM:
            return self.refuse(msg, av.content.get("reason", "Could not check availability."))
        if av.content["event_id"] != event_id or av.content["event_status"] != "published" or av.content["event_started"]:
            return self.refuse(msg, "This event is not open for booking.")
        if av.content["remaining"] >= qty:                                                     # W1
            return self.refuse(msg, f"{av.content['remaining']} ticket(s) are still available - please book directly.")
        active = self.db.scalar(
            "SELECT COUNT(*) FROM waitlist WHERE user_id=:u AND category_id=:c AND status IN ('waiting','offered','claiming')",
            u=user_id, c=category_id,
        )
        if active:
            return self.refuse(msg, "You are already on the waitlist for this ticket type.")
        entry_id = self.db.insert(
            "INSERT INTO waitlist(event_id, category_id, user_id, quantity, status, created_at) VALUES (:e, :c, :u, :q, 'waiting', :t)",
            e=event_id, c=category_id, u=user_id, q=qty, t=fmt(clock.now()),
        )
        position = self.db.scalar(
            "SELECT COUNT(*) FROM waitlist WHERE category_id=:c AND status='waiting' AND id <= :i", c=category_id, i=entry_id
        )
        self.incr("joined")
        return self.agree(msg, waitlist_id=entry_id, position=position)

    # ------------------------------------------------------------- allocate
    def _allocate(self, category_id: int, conv: str) -> int:
        offered = 0
        waiting = self.db.query(
            "SELECT w.*, e.title AS event_title FROM waitlist w JOIN events e ON e.id=w.event_id "
            "WHERE w.category_id=:c AND w.status='waiting' ORDER BY w.id", c=category_id,
        )
        for entry in waiting:                                                                  # W2
            hold = self.ask("BookingAgent", "hold_seats", conv, category_id=category_id, qty=entry["quantity"])  # W3
            if hold.performative != Performative.AGREE:
                continue
            expires = clock.now() + timedelta(minutes=self.hold_minutes)
            changed = self.db.execute(
                "UPDATE waitlist SET status='offered', offered_at=:n, expires_at=:x WHERE id=:i AND status='waiting'",
                n=fmt(clock.now()), x=fmt(expires), i=entry["id"],
            )
            if changed != 1:  # left the list in the meantime: give the seats back
                self.ask("BookingAgent", "release_hold", conv, category_id=category_id, qty=entry["quantity"])
                continue
            offered += 1
            self.incr("offers_made")
            self.announce("seats_offered", conv, user_id=entry["user_id"], waitlist_id=entry["id"], event_id=entry["event_id"],
                          event_title=entry["event_title"], quantity=entry["quantity"], expires_at=fmt(expires))
        return offered

    def on_event_seats_freed(self, msg):  # W5 reactive behaviour
        self._allocate(int(msg.content["category_id"]), msg.conversation_id)

    # ---------------------------------------------------------------- claim
    def on_claim(self, msg):
        c = msg.content
        entry = self.db.one("SELECT * FROM waitlist WHERE id=:i", i=int(c["waitlist_id"]))
        if not entry or entry["user_id"] != int(c["user_id"]):
            return self.refuse(msg, "Waitlist entry not found.")
        if entry["status"] != "offered":
            return self.refuse(msg, f"This offer is no longer available ({entry['status']}).")
        claimed = self.db.execute(
            "UPDATE waitlist SET status='claiming' WHERE id=:i AND status='offered' AND expires_at > :n",
            i=entry["id"], n=fmt(clock.now()),
        )
        if claimed != 1:
            return self.refuse(msg, "Sorry, your hold has expired.")
        result = self.ask(
            "BookingAgent", "book", msg.conversation_id, user_id=entry["user_id"], event_id=entry["event_id"], held=True,
            items=[{"category_id": entry["category_id"], "qty": entry["quantity"]}],
            simulate_failure=bool(c.get("simulate_failure")),
        )
        if result.performative == Performative.AGREE:
            self.db.execute("UPDATE waitlist SET status='claimed', booking_id=:b WHERE id=:i", b=result.content["booking_id"], i=entry["id"])
            self.incr("claimed")
            return self.agree(msg, booking_id=result.content["booking_id"])
        self.db.execute("UPDATE waitlist SET status='offered' WHERE id=:i AND status='claiming'", i=entry["id"])
        return self.refuse(msg, result.content.get("reason", "Booking failed; your hold is still active."))

    def on_leave(self, msg):
        entry = self.db.one("SELECT * FROM waitlist WHERE id=:i", i=int(msg.content["waitlist_id"]))
        if not entry or entry["user_id"] != int(msg.content["user_id"]):
            return self.refuse(msg, "Waitlist entry not found.")
        was = entry["status"]
        if was not in ("waiting", "offered"):
            return self.refuse(msg, f"Entry is already {was}.")
        if self.db.execute("UPDATE waitlist SET status='cancelled' WHERE id=:i AND status=:s", i=entry["id"], s=was) != 1:
            return self.refuse(msg, "Entry changed, please refresh.")
        if was == "offered":
            self.ask("BookingAgent", "release_hold", msg.conversation_id, category_id=entry["category_id"], qty=entry["quantity"])
            self._allocate(entry["category_id"], msg.conversation_id)
        return self.agree(msg, status="cancelled")

    # ---------------------------------------------------- timer (proactive)
    def on_sweep(self, msg):
        """Runs on a timer with no user action: expire unclaimed holds, then re-offer the seats."""
        conv, now = msg.conversation_id, clock.now()
        due = self.db.query(
            "SELECT w.*, e.title AS event_title FROM waitlist w JOIN events e ON e.id=w.event_id "
            "WHERE w.status='offered' AND w.expires_at <= :n", n=fmt(now),
        )
        expired, categories = 0, set()
        for entry in due:                                                                      # W4
            if self.db.execute("UPDATE waitlist SET status='expired' WHERE id=:i AND status='offered'", i=entry["id"]) != 1:
                continue
            self.ask("BookingAgent", "release_hold", conv, category_id=entry["category_id"], qty=entry["quantity"])
            self.announce("hold_expired", conv, user_id=entry["user_id"], event_id=entry["event_id"], event_title=entry["event_title"])
            expired += 1
            categories.add(entry["category_id"])
        reoffered = sum(self._allocate(cid, conv) for cid in categories)
        self.incr("sweeps")
        self.incr("holds_expired", expired)
        self.set_state("last_sweep_at", fmt(now))
        return self.inform(msg, expired=expired, reoffered=reoffered)

    def on_event_event_cancelled(self, msg):  # W5 reactive behaviour
        event_id = int(msg.content["event_id"])
        entries = self.db.query(
            "SELECT * FROM waitlist WHERE event_id=:e AND status IN ('waiting','offered','claiming')", e=event_id
        )
        for entry in entries:
            self.db.execute("UPDATE waitlist SET status='cancelled' WHERE id=:i", i=entry["id"])
        if entries:
            self.announce("waitlist_cleared", msg.conversation_id, event_id=event_id,
                          event_title=msg.content.get("event_title", ""), user_ids=sorted({e["user_id"] for e in entries}))
