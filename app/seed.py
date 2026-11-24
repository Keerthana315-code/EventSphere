"""Demo data: three demo accounts, venues and events (dates are relative to 'now')."""
from datetime import timedelta

from . import clock, repo, services
from .clock import fmt


def seed_demo(system, password: str) -> bool:
    """Idempotent: does nothing if users already exist. Returns True when data was created."""
    db = system.db
    if db.scalar("SELECT COUNT(*) FROM users"):
        return False
    admin = repo.create_user(db, "Demo Admin", "admin@eventsphere.demo", password, "admin")
    repo.create_user(db, "Demo Gate Staff", "staff@eventsphere.demo", password, "staff")
    repo.create_user(db, "Demo Attendee", "attendee@eventsphere.demo", password, "attendee")

    hall = repo.create_venue(db, dict(
        name="Main Auditorium", location="University of Vavuniya, Vavuniya", capacity=300, hourly_rate=15000,
        description="Large auditorium with stage, lighting and sound.", image_url="", open_for_hire=True))
    seminar = repo.create_venue(db, dict(
        name="Seminar Room A", location="Faculty of Technological Studies", capacity=60, hourly_rate=4000,
        description="Air-conditioned room for workshops and club meetings.", image_url="", open_for_hire=True))
    repo.create_venue(db, dict(
        name="Open Air Theatre", location="Campus Grounds", capacity=500, hourly_rate=9000,
        description="Open-air stage for concerts (events only).", image_url="", open_for_hire=False))

    day = (clock.now() + timedelta(days=10)).replace(hour=18, minute=0, second=0)
    samples = [
        (hall, "Campus Music Night", "Concert", day, 3, "An evening of live music.",
         [("Standard", 1000, 200), ("VIP", 2500, 50)]),
        (seminar, "Intro to AI Agents Workshop", "Workshop", day + timedelta(days=2, hours=-8), 2,
         "Hands-on workshop on multi-agent systems.", [("General", 500, 3)]),  # tiny: easy to test sold-out + waitlist
        (hall, "Tech Careers Seminar", "Seminar", day + timedelta(days=5, hours=-9), 2,
         "Industry speakers talk about internships and careers.", [("Free entry", 0, 150)]),
    ]
    for venue_id, title, category, start, hours, description, cats in samples:
        services.create_event(
            system, admin_id=admin, title=title, category=category, venue_id=venue_id, start=fmt(start),
            end=fmt(start + timedelta(hours=hours)), description=description,
            categories=[{"name": n, "price": p, "quantity": q} for n, p, q in cats], publish=True)
    return True
