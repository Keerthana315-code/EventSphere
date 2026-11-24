import os
from datetime import datetime

import pytest

os.environ.setdefault("PASSWORD_ITERATIONS", "1000")  # fast hashing in tests only

from app import clock, repo, services  # noqa: E402
from app.db import Database  # noqa: E402
from app.system import System  # noqa: E402

NOW = datetime(2026, 11, 14, 12, 0, 0)  # a Saturday


@pytest.fixture(autouse=True)
def frozen_clock():
    clock.set_now(NOW)
    yield
    clock.set_now(None)


@pytest.fixture
def db(tmp_path):
    return Database(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def system(db):
    return System(db, hold_minutes=10)


class World:
    """Small helper that builds users, a venue and an event for tests."""

    def __init__(self, system):
        self.system, self.db = system, system.db
        self.admin = repo.create_user(self.db, "Admin", "admin@test.io", "password1", "admin")
        self.staff = repo.create_user(self.db, "Staff", "staff@test.io", "password1", "staff")
        self.alice = repo.create_user(self.db, "Alice", "alice@test.io", "password1")
        self.bob = repo.create_user(self.db, "Bob", "bob@test.io", "password1")
        self.venue = repo.create_venue(self.db, dict(
            name="Hall", location="Campus", capacity=100, hourly_rate=1000, description="", image_url="", open_for_hire=True))

    def make_event(self, start="2026-11-25 18:00:00", end="2026-11-25 20:00:00", quantity=5, price=1000.0,
                   venue=None, publish=True, title="Test Event"):
        return services.create_event(
            self.system, admin_id=self.admin, title=title, category="Concert", venue_id=venue or self.venue,
            start=start, end=end, description="", categories=[{"name": "Std", "price": price, "quantity": quantity}],
            publish=publish)

    def category(self, event_id):
        return self.db.one("SELECT * FROM ticket_categories WHERE event_id=:e", e=event_id)

    def book(self, user, event_id, qty=1, **kw):
        cat = self.category(event_id)
        return services.book(self.system, user, event_id, [{"category_id": cat["id"], "qty": qty}], **kw)


@pytest.fixture
def world(system):
    return World(system)
