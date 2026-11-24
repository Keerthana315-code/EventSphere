"""Wires the database, the message bus and the five agents together."""
import logging
import threading

from .agents.booking_agent import BookingAgent
from .agents.notification_agent import NotificationAgent
from .agents.ticket_agent import TicketAgent
from .agents.venue_agent import VenueAgent
from .agents.waitlist_agent import WaitlistAgent
from .bus import MessageBus

log = logging.getLogger("eventsphere.scheduler")


class System:
    def __init__(self, db, hold_minutes: int | None = None):
        self.db = db
        self.bus = MessageBus(db)
        self.agents = [
            VenueAgent(db, self.bus),
            BookingAgent(db, self.bus),
            TicketAgent(db, self.bus),
            WaitlistAgent(db, self.bus, hold_minutes),
            NotificationAgent(db, self.bus),
        ]
        for agent in self.agents:
            self.bus.register(agent)

    def agent(self, name: str):
        return self.bus.agents[name]

    def sweep(self):
        """One WaitlistAgent expiry sweep (also called by the scheduler thread)."""
        return self.bus.request("Scheduler", "WaitlistAgent", "sweep")


class Scheduler:
    """Background thread: makes the WaitlistAgent act with no user action (proactive behaviour)."""

    def __init__(self, system: System, interval_seconds: int):
        self.system, self.interval = system, interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="waitlist-sweeper", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                self.system.sweep()
            except Exception:
                log.exception("sweep failed")
