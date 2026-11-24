"""Single source of truth for every agent decision rule.

Each constant here is quoted in docs/REPORT.md. Agents import from this module,
never from each other.
"""

# ---- BookingAgent -----------------------------------------------------------
MAX_TICKETS_PER_REQUEST = 6          # refuse bookings of more than 6 tickets
MAX_TICKETS_PER_USER_PER_EVENT = 10  # fairness: one person cannot hoard an event
REFUND_FULL_HOURS = 7 * 24           # >= 7 days before start  -> 100 % refund
REFUND_PARTIAL_HOURS = 48            # >= 48 hours before start -> 50 % refund
REFUND_PARTIAL_PERCENT = 50          # < 48 hours                -> 0 % refund


def refund_percent(hours_before_start: float) -> int:
    """Stated refund policy used by BookingAgent and shown to attendees."""
    if hours_before_start >= REFUND_FULL_HOURS:
        return 100
    if hours_before_start >= REFUND_PARTIAL_HOURS:
        return REFUND_PARTIAL_PERCENT
    return 0


REFUND_POLICY_TEXT = (
    "Refund policy: 100% if you cancel 7 or more days before the event, "
    "50% from 7 days down to 48 hours before, 0% in the last 48 hours. "
    "If the organiser cancels the event you always get 100%."
)

# ---- VenueAgent -------------------------------------------------------------
TURNAROUND_BUFFER_MIN = 30           # gap needed between two activities at a venue
HIRE_MIN_HOURS = 1
HIRE_MAX_HOURS = 12
HIRE_ROUTINE_MAX_HOURS = 6           # longer hires are escalated to the admin
HIRE_ROUTINE_MAX_FILL = 0.8          # > 80 % of capacity is escalated
HIRE_MIN_NOTICE_HOURS = 2
HIRE_MAX_ADVANCE_DAYS = 180
ROUTINE_EARLIEST_HOUR = 8            # routine hires must sit inside 08:00-22:00
ROUTINE_LATEST_END_HOUR = 22
WEEKEND_SURCHARGE = 0.25             # Sat/Sun
EVENING_SURCHARGE = 0.10             # start at or after 18:00
EVENING_START_HOUR = 18

# ---- TicketAgent ------------------------------------------------------------
CHECKIN_OPENS_MIN_BEFORE_START = 120  # doors open 2 hours before start
SUSPICIOUS_REJECTED_SCANS = 2         # 2 rejected re-scans => flag as possible shared screenshot

EVENT_CATEGORIES = ["Concert", "Workshop", "Seminar", "Conference", "Other"]
