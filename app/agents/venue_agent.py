"""VenueAgent - goal: keep every venue's calendar free of clashes.

Decision rules (see docs/REPORT.md section 4):
  V1  refuse a slot if end <= start or the venue does not exist
  V2  refuse an event whose total tickets exceed the venue capacity
  V3  refuse a slot that overlaps another activity, counting a 30-minute turnaround buffer
  V4  private hire: refuse if the venue is not open for hire, guests < 1, duration outside 1-12 h,
      less than 2 h notice, or more than 180 days ahead
  V5  private hire with too many guests or a clash -> PROPOSE alternative times / venues
  V6  private hire that is "routine" (<= 6 h, <= 80 % of capacity, inside 08:00-22:00) is CONFIRMED
      automatically; anything else is ESCALATED to the admin and the time is held meanwhile
  V7  price = hourly rate x hours, +25 % on weekends, +10 % for evening starts (>= 18:00)
"""
import threading
from datetime import timedelta

from .. import clock, rules
from ..clock import fmt, parse
from .base import Agent


def price_hire(rate: float, start, end) -> dict:
    hours = (end - start).total_seconds() / 3600
    base = rate * hours
    weekend = rules.WEEKEND_SURCHARGE if start.weekday() >= 5 else 0.0
    evening = rules.EVENING_SURCHARGE if start.hour >= rules.EVENING_START_HOUR else 0.0
    total = round(base * (1 + weekend + evening), 2)
    return {
        "hours": round(hours, 2), "rate": rate, "base": round(base, 2),
        "weekend_surcharge_pct": int(weekend * 100), "evening_surcharge_pct": int(evening * 100),
        "total": total,
    }


class VenueAgent(Agent):
    name = "VenueAgent"
    goal = "Keep every venue's calendar free of clashes"

    def __init__(self, db, bus):
        super().__init__(db, bus)
        self._calendar_lock = threading.Lock()

    # ---------------------------------------------------------------- calendar
    def _venue(self, venue_id):
        return self.db.one("SELECT * FROM venues WHERE id=:i", i=venue_id)

    def _slots(self, venue_id):
        return self.db.query("SELECT * FROM calendar_slots WHERE venue_id=:v AND status='active'", v=venue_id)

    @staticmethod
    def _clash(slots, start, end):
        buffer = timedelta(minutes=rules.TURNAROUND_BUFFER_MIN)
        for s in slots:
            if parse(s["start_time"]) < end + buffer and parse(s["end_time"]) + buffer > start:
                return s
        return None

    def _describe(self, slot) -> str:
        if slot["kind"] == "event":
            ev = self.db.one("SELECT title FROM events WHERE id=:i", i=slot["ref_id"])
            what = f"event '{ev['title']}'" if ev else "another event"
        else:
            what = "a private hire"
        return f"{what} ({slot['start_time'][:16]} to {slot['end_time'][11:16]})"

    def _reserve(self, venue_id, kind, ref_id, start, end):
        """Atomically check for clashes and insert the slot. Returns (slot_id, clashing_slot)."""
        with self._calendar_lock, self.db.tx() as t:
            if self.db.is_pg:
                t.execute("SELECT pg_advisory_xact_lock(:v)", v=venue_id)
            slots = t.query("SELECT * FROM calendar_slots WHERE venue_id=:v AND status='active'", v=venue_id)
            clash = self._clash(slots, start, end)
            if clash:
                return None, clash
            slot_id = t.insert(
                "INSERT INTO calendar_slots(venue_id, kind, ref_id, start_time, end_time, status, created_at) "
                "VALUES (:v, :k, :r, :s, :e, 'active', :c)",
                v=venue_id, k=kind, r=ref_id, s=fmt(start), e=fmt(end), c=fmt(clock.now()),
            )
            return slot_id, None

    def _release(self, kind, ref_id) -> int:
        return self.db.execute(
            "UPDATE calendar_slots SET status='released' WHERE kind=:k AND ref_id=:r AND status='active'",
            k=kind, r=ref_id,
        )

    # ------------------------------------------------------------ alternatives
    def _alt_times(self, venue, start, end, limit=3, with_price=False):
        duration = end - start
        earliest = clock.now() + timedelta(hours=rules.HIRE_MIN_NOTICE_HOURS)
        slots = self._slots(venue["id"])
        found = []
        for day_offset in (0, 1, 2):
            day = (start + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0)
            for hour in range(rules.ROUTINE_EARLIEST_HOUR, rules.ROUTINE_LATEST_END_HOUR):
                cs = day.replace(hour=hour)
                ce = cs + duration
                if ce.date() != cs.date() or ce.hour * 60 + ce.minute > rules.ROUTINE_LATEST_END_HOUR * 60:
                    continue
                if cs == start or cs < earliest or self._clash(slots, cs, ce):
                    continue
                found.append((abs((cs - start).total_seconds()), cs, ce))
        found.sort(key=lambda x: x[0])
        out = []
        for _, cs, ce in found[:limit]:
            opt = {"venue_id": venue["id"], "venue_name": venue["name"], "start": fmt(cs), "end": fmt(ce)}
            if with_price:
                opt["price"] = price_hire(venue["hourly_rate"], cs, ce)["total"]
            out.append(opt)
        return out

    def _alt_venues(self, start, end, guests, hire, exclude_id, limit=3):
        out = []
        for v in self.db.query("SELECT * FROM venues ORDER BY capacity"):
            if v["id"] == exclude_id or v["capacity"] < guests or (hire and not v["open_for_hire"]):
                continue
            if self._clash(self._slots(v["id"]), start, end):
                continue
            out.append({
                "venue_id": v["id"], "venue_name": v["name"], "start": fmt(start), "end": fmt(end),
                "price": price_hire(v["hourly_rate"], start, end)["total"] if hire else None,
            })
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------ event slots
    def on_reserve_slot(self, msg):
        c = msg.content
        try:
            venue_id, start, end = int(c["venue_id"]), parse(c["start"]), parse(c["end"])
            tickets = int(c.get("tickets_total", 0))
            ref_id = int(c["ref_id"])
        except (KeyError, ValueError, TypeError):
            return self.refuse(msg, "Invalid slot request (venue, start, end and ref_id are required).")
        venue = self._venue(venue_id)
        if not venue:
            return self.refuse(msg, "Venue does not exist.")                                   # V1
        if end <= start:
            return self.refuse(msg, "End time must be after the start time.")                  # V1
        if tickets > venue["capacity"]:                                                        # V2
            self.incr("slots_refused")
            return self.refuse(msg, f"Total tickets ({tickets}) exceed the capacity of {venue['name']} ({venue['capacity']}).")
        slot_id, clash = self._reserve(venue_id, c.get("kind", "event"), ref_id, start, end)
        if clash:                                                                              # V3
            self.incr("slots_refused")
            return self.refuse(
                msg,
                f"{venue['name']} is not free: it clashes with {self._describe(clash)} "
                f"(a {rules.TURNAROUND_BUFFER_MIN}-minute turnaround buffer applies).",
                suggestions={
                    "alternative_times": self._alt_times(venue, start, end),
                    "alternative_venues": self._alt_venues(start, end, tickets, False, venue_id),
                },
            )
        self.incr("slots_granted")
        return self.agree(msg, slot_id=slot_id)

    def on_release_slot(self, msg):
        n = self._release(msg.content.get("kind", "event"), int(msg.content["ref_id"]))
        return self.inform(msg, released=n)

    def on_event_event_cancelled(self, msg):  # reactive: free the calendar when an event is cancelled
        self._release("event", int(msg.content["event_id"]))

    # -------------------------------------------------------------- hire price
    def on_quote(self, msg):
        c = msg.content
        venue = self._venue(int(c["venue_id"]))
        if not venue:
            return self.refuse(msg, "Venue does not exist.")
        return self.inform(msg, quote=price_hire(venue["hourly_rate"], parse(c["start"]), parse(c["end"])))

    # ----------------------------------------------------------- private hire
    def _store_hire(self, user_id, venue_id, start, end, purpose, guests, status, price, reason) -> int:
        return self.db.insert(
            "INSERT INTO hire_requests(user_id, venue_id, start_time, end_time, purpose, guests, status, price, reason, created_at) "
            "VALUES (:u, :v, :s, :e, :p, :g, :st, :pr, :r, :c)",
            u=user_id, v=venue_id, s=fmt(start), e=fmt(end), p=purpose, g=guests, st=status, pr=price, r=reason,
            c=fmt(clock.now()),
        )

    def on_hire_request(self, msg):
        c = msg.content
        try:
            user_id, venue_id, guests = int(c["user_id"]), int(c["venue_id"]), int(c["guests"])
            start, end = parse(c["start"]), parse(c["end"])
        except (KeyError, ValueError, TypeError):
            return self.refuse(msg, "Invalid request: venue, start, end and guest count are required.")
        purpose = str(c.get("purpose", "")).strip()[:200]
        venue = self._venue(venue_id)
        now = clock.now()

        def decline(reason, **extra):
            hid = self._store_hire(user_id, venue_id, start, end, purpose, guests, "declined", 0, reason)
            self.incr("hires_declined")
            return self.refuse(msg, reason, hire_id=hid, **extra)

        if not venue:
            return self.refuse(msg, "Venue does not exist.")
        if not venue["open_for_hire"]:                                                          # V4
            return decline(f"{venue['name']} is not open for private hire.",
                           suggestions={"alternative_venues": self._alt_venues(start, end, guests, True, venue_id)})
        if guests < 1:
            return decline("Guest count must be at least 1.")
        if end <= start:
            return decline("End time must be after the start time.")
        hours = (end - start).total_seconds() / 3600
        if hours < rules.HIRE_MIN_HOURS or hours > rules.HIRE_MAX_HOURS:
            return decline(f"A hire must last between {rules.HIRE_MIN_HOURS} and {rules.HIRE_MAX_HOURS} hours (requested {hours:.1f}).")
        if start < now + timedelta(hours=rules.HIRE_MIN_NOTICE_HOURS):
            return decline(f"Requests need at least {rules.HIRE_MIN_NOTICE_HOURS} hours notice.")
        if start > now + timedelta(days=rules.HIRE_MAX_ADVANCE_DAYS):
            return decline(f"Requests can be made at most {rules.HIRE_MAX_ADVANCE_DAYS} days ahead.")

        quote = price_hire(venue["hourly_rate"], start, end)
        if guests > venue["capacity"]:                                                          # V5
            options = self._alt_venues(start, end, guests, True, venue_id)
            reason = f"{venue['name']} holds {venue['capacity']} guests but you need {guests}."
            return self._propose_or_refuse(msg, decline, user_id, venue_id, start, end, purpose, guests, reason, options)

        slot_id, clash = self._reserve(venue_id, "hire", 0, start, end)
        if clash:                                                                               # V5
            options = self._alt_times(venue, start, end, limit=3, with_price=True)
            options += self._alt_venues(start, end, guests, True, venue_id, limit=2)
            reason = f"{venue['name']} is not free then: it clashes with {self._describe(clash)}."
            return self._propose_or_refuse(msg, decline, user_id, venue_id, start, end, purpose, guests, reason, options)

        routine = (
            hours <= rules.HIRE_ROUTINE_MAX_HOURS
            and guests <= rules.HIRE_ROUTINE_MAX_FILL * venue["capacity"]
            and start.hour >= rules.ROUTINE_EARLIEST_HOUR
            and end.date() == start.date()
            and end.hour * 60 + end.minute <= rules.ROUTINE_LATEST_END_HOUR * 60
        )
        status = "confirmed" if routine else "pending"                                          # V6
        reason = "Routine request confirmed automatically." if routine else (
            "Needs admin approval: long hire, large group or outside 08:00-22:00. The time is held for you meanwhile.")
        hid = self._store_hire(user_id, venue_id, start, end, purpose, guests, status, quote["total"], reason)
        self.db.execute("UPDATE calendar_slots SET ref_id=:h WHERE id=:s", h=hid, s=slot_id)
        info = dict(hire_id=hid, user_id=user_id, venue_name=venue["name"], start=fmt(start), end=fmt(end),
                    guests=guests, price=quote["total"], purpose=purpose)
        if routine:
            self.incr("hires_auto_confirmed")
            self.announce("hire_decided", msg.conversation_id, status="confirmed", **info)
            return self.agree(msg, status="confirmed", reason=reason, quote=quote, **info)
        self.incr("hires_escalated")
        self.announce("hire_escalated", msg.conversation_id, **info)
        return self.inform(msg, status="escalated", reason=reason, quote=quote, **info)

    def _propose_or_refuse(self, msg, decline, user_id, venue_id, start, end, purpose, guests, reason, options):
        if not options:
            return decline(reason + " No alternative time or venue is available nearby.")
        hid = self._store_hire(user_id, venue_id, start, end, purpose, guests, "declined", 0, reason)
        self.incr("hires_countered")
        return self.propose(msg, reason, options, hire_id=hid)

    def on_decide_hire(self, msg):
        c = msg.content
        hire = self.db.one("SELECT * FROM hire_requests WHERE id=:i", i=int(c["hire_id"]))
        if not hire:
            return self.refuse(msg, "Hire request not found.")
        if hire["status"] != "pending":
            return self.refuse(msg, f"This request is already {hire['status']}.")
        approve = bool(c.get("approve"))
        note = str(c.get("note", "")).strip()
        status = "confirmed" if approve else "rejected"
        reason = note or ("Approved by the admin." if approve else "Rejected by the admin.")
        changed = self.db.execute(
            "UPDATE hire_requests SET status=:s, reason=:r, decided_by=:d WHERE id=:i AND status='pending'",
            s=status, r=reason, d=c.get("admin_id"), i=hire["id"],
        )
        if changed != 1:
            return self.refuse(msg, "This request was already decided.")
        if not approve:
            self._release("hire", hire["id"])
        venue = self._venue(hire["venue_id"])
        self.announce("hire_decided", msg.conversation_id, status=status, hire_id=hire["id"],
                      user_id=hire["user_id"], venue_name=venue["name"], start=hire["start_time"],
                      end=hire["end_time"], price=hire["price"], reason=reason)
        return self.agree(msg, status=status)
