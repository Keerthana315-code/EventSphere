"""TicketAgent - goal: admit each ticket exactly once.

Decision rules (the answer to a scan is one of: admit, already_used, wrong_event, cancelled,
outside_window, unknown):
  T1  every ticket gets a unique, unguessable code (secrets.token_urlsafe, 144 bits)
  T2  unknown code                          -> REFUSE unknown
  T3  ticket belongs to another event       -> REFUSE wrong_event
  T4  ticket cancelled / event cancelled    -> REFUSE cancelled
  T5  ticket already used                   -> REFUSE already_used (shows when it was admitted)
  T6  before doors open (2 h before start) or after the event has ended -> REFUSE outside_window
  T7  otherwise admit with ONE atomic UPDATE (status valid -> used), so two scanners racing on
      the same ticket cannot both admit it
  T8  belief ``scan:<code>``: after 2 rejected re-scans the ticket is flagged "suspicious"
      (possible shared screenshot) and the admins are told
"""
import secrets
from datetime import timedelta

from .. import clock, rules
from ..clock import fmt, parse
from .base import Agent


class TicketAgent(Agent):
    name = "TicketAgent"
    goal = "Admit each ticket exactly once"

    def on_issue_tickets(self, msg):
        c = msg.content
        codes = []
        with self.db.tx() as t:
            for item in c["items"]:
                for _ in range(int(item["qty"])):
                    code = secrets.token_urlsafe(18)                                           # T1
                    t.insert(
                        "INSERT INTO tickets(booking_id, event_id, category_id, user_id, code, status, price, issued_at) "
                        "VALUES (:b, :e, :c, :u, :code, 'valid', :p, :t)",
                        b=c["booking_id"], e=c["event_id"], c=item["category_id"], u=c["user_id"],
                        code=code, p=item.get("price", 0), t=fmt(clock.now()),
                    )
                    codes.append(code)
        self.incr("tickets_issued", len(codes))
        return self.inform(msg, codes=codes, count=len(codes))

    def on_cancel_tickets(self, msg):
        n = self.db.execute(
            "UPDATE tickets SET status='cancelled' WHERE booking_id=:b AND status='valid'", b=int(msg.content["booking_id"])
        )
        return self.inform(msg, cancelled=n)

    def _remember(self, code, result):
        belief = self.get_state("scan:" + code, {"attempts": 0, "rejected": 0, "flagged": False})
        belief["attempts"] += 1
        belief["last_result"] = result
        belief["last_scan_at"] = fmt(clock.now())
        if result == "admit":
            belief["admitted_at"] = fmt(clock.now())
        elif result == "already_used":
            belief["rejected"] += 1
        self.set_state("scan:" + code, belief)
        return belief

    def on_scan(self, msg):
        c = msg.content
        code = str(c.get("code", "")).strip()
        try:
            event_id = int(c["event_id"])
        except (KeyError, ValueError, TypeError):
            return self.refuse(msg, "Choose the event you are scanning for.", result="unknown")
        ticket = self.db.one(
            "SELECT t.*, k.name AS category_name, u.name AS holder, e.title AS event_title, e.status AS event_status, "
            "e.start_time, e.end_time FROM tickets t JOIN ticket_categories k ON k.id=t.category_id "
            "JOIN users u ON u.id=t.user_id JOIN events e ON e.id=t.event_id WHERE t.code=:c", c=code,
        )
        if not ticket:                                                                         # T2
            self.incr("scans_rejected")
            return self.refuse(msg, "This code is not a valid ticket.", result="unknown")
        info = dict(holder=ticket["holder"], category=ticket["category_name"], event=ticket["event_title"])

        def reject(result, reason, remember=True):
            self.incr("scans_rejected")
            belief = self._remember(code, result) if remember else {}
            if belief.get("rejected", 0) >= rules.SUSPICIOUS_REJECTED_SCANS and not belief.get("flagged"):  # T8
                belief["flagged"] = True
                self.set_state("scan:" + code, belief)
                self.announce("suspicious_scan", msg.conversation_id, code_prefix=code[:6], event_id=ticket["event_id"],
                              event_title=ticket["event_title"], holder=ticket["holder"], rejected=belief["rejected"])
            return self.refuse(msg, reason, result=result, suspicious=bool(belief.get("flagged")), **info)

        if ticket["event_id"] != event_id:                                                     # T3
            return reject("wrong_event", f"Wrong event: this ticket is for '{ticket['event_title']}'.", remember=False)
        if ticket["status"] == "cancelled" or ticket["event_status"] == "cancelled":           # T4
            return reject("cancelled", "This ticket has been cancelled.")
        if ticket["status"] == "used":                                                         # T5
            return reject("already_used", f"Already used at {ticket['used_at'][11:16]} on {ticket['used_at'][:10]}.")
        start, end, now = parse(ticket["start_time"]), parse(ticket["end_time"]), clock.now()
        opens = start - timedelta(minutes=rules.CHECKIN_OPENS_MIN_BEFORE_START)
        if now < opens:                                                                        # T6
            return reject("outside_window", f"Check-in is not open yet (doors open {fmt(opens)[11:16]}).", remember=False)
        if now > end:
            return reject("outside_window", "Check-in is closed: the event has ended.", remember=False)
        changed = self.db.execute(                                                             # T7
            "UPDATE tickets SET status='used', used_at=:n, used_by=:s WHERE id=:i AND status='valid'",
            n=fmt(now), s=c.get("staff_id"), i=ticket["id"],
        )
        if changed != 1:
            return reject("already_used", "Already used (another scanner admitted it a moment ago).")
        self._remember(code, "admit")
        self.incr("admitted")
        return self.agree(msg, result="admit", **info)
