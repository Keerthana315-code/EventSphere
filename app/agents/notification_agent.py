"""NotificationAgent - goal: tell the right person what affects them.

It is a pure listener: it reacts to broadcast INFORM events from the other agents and turns them
into notifications (stored for the in-app inbox).
  N1  booking_confirmed / booking_cancelled -> the attendee
  N2  event_cancelled / waitlist_cleared    -> every affected attendee (with refund amount)
  N3  seats_offered / hold_expired          -> the waiting attendee
  N4  hire_decided                          -> the person who asked for the hire
  N5  hire_escalated / suspicious_scan      -> every admin
"""
from .. import clock
from ..clock import fmt
from ..config import get_settings
from .base import Agent


class NotificationAgent(Agent):
    name = "NotificationAgent"
    goal = "Tell the right person what affects them"

    def _money(self, amount) -> str:
        return f"{get_settings().currency} {float(amount):,.2f}"

    def _notify(self, user_id, title, body, link=""):
        self.db.execute(
            "INSERT INTO notifications(user_id, title, body, link, created_at) VALUES (:u, :t, :b, :l, :c)",
            u=user_id, t=title, b=body, l=link, c=fmt(clock.now()),
        )
        self.incr("notifications_sent")

    def _notify_admins(self, title, body, link=""):
        for admin in self.db.query("SELECT id FROM users WHERE role='admin'"):
            self._notify(admin["id"], title, body, link)

    def on_event_booking_confirmed(self, msg):
        c = msg.content
        self._notify(c["user_id"], "Booking confirmed",
                     f"{c['count']} ticket(s) for {c['event_title']} - {self._money(c['total'])} (ref {c['payment_ref']}).",
                     f"/bookings/{c['booking_id']}")

    def on_event_booking_cancelled(self, msg):
        c = msg.content
        self._notify(c["user_id"], "Booking cancelled",
                     f"Your booking for {c['event_title']} was cancelled. Refund: {self._money(c['refund'])} ({c['percent']}%).",
                     "/my/bookings")

    def on_event_event_cancelled(self, msg):
        c = msg.content
        for refund in c.get("refunds", []):
            self._notify(refund["user_id"], "Event cancelled",
                         f"{c['event_title']} was cancelled ({c['reason']}). Full refund: {self._money(refund['amount'])}.",
                         "/my/bookings")

    def on_event_waitlist_cleared(self, msg):
        c = msg.content
        for user_id in c.get("user_ids", []):
            self._notify(user_id, "Waitlist closed", f"{c['event_title']} was cancelled, so the waitlist was closed.")

    def on_event_seats_offered(self, msg):
        c = msg.content
        self._notify(c["user_id"], "Seats available - claim now!",
                     f"{c['quantity']} seat(s) for {c['event_title']} are held for you until {c['expires_at'][11:16]}.",
                     "/my/bookings")

    def on_event_hold_expired(self, msg):
        c = msg.content
        self._notify(c["user_id"], "Hold expired", f"Your held seats for {c['event_title']} expired and were offered to the next person.")

    def on_event_hire_decided(self, msg):
        c = msg.content
        verdict = "confirmed" if c["status"] == "confirmed" else "rejected"
        self._notify(c["user_id"], f"Venue hire {verdict}",
                     f"{c['venue_name']} on {c['start'][:16]}: {verdict}. Price {self._money(c['price'])}.", "/hire/mine")

    def on_event_hire_escalated(self, msg):
        c = msg.content
        self._notify_admins("Hire request needs approval",
                            f"{c['venue_name']}, {c['start'][:16]} to {c['end'][11:16]}, {c['guests']} guests.", "/admin/hires")

    def on_event_suspicious_scan(self, msg):
        c = msg.content
        self._notify_admins("Suspicious ticket scans",
                            f"A ticket for {c['event_title']} (holder {c['holder']}, code {c['code_prefix']}...) was rejected {c['rejected']} times - possible shared screenshot.",
                            "/admin")
