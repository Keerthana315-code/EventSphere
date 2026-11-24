"""Tiny database layer that runs the same SQL on SQLite (dev) and PostgreSQL (production).

SQL is written with named parameters (:name). Every call opens its own connection, so
the code is safe to use from many threads. Single statements are atomic; use
``with db.tx() as t:`` when several statements must succeed or fail together.
"""
import re
import sqlite3
from contextlib import contextmanager

_PARAM = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id {PK}, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'attendee', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS venues (
    id {PK}, name TEXT NOT NULL, location TEXT NOT NULL, capacity INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '', image_url TEXT NOT NULL DEFAULT '',
    hourly_rate DOUBLE PRECISION NOT NULL DEFAULT 0, open_for_hire INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
    id {PK}, title TEXT NOT NULL, category TEXT NOT NULL, venue_id INTEGER NOT NULL REFERENCES venues(id),
    start_time TEXT NOT NULL, end_time TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft', created_by INTEGER, created_at TEXT NOT NULL, cancel_reason TEXT);
CREATE TABLE IF NOT EXISTS ticket_categories (
    id {PK}, event_id INTEGER NOT NULL REFERENCES events(id), name TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL, quantity INTEGER NOT NULL, sold INTEGER NOT NULL DEFAULT 0,
    CHECK (sold >= 0 AND sold <= quantity));
CREATE TABLE IF NOT EXISTS bookings (
    id {PK}, user_id INTEGER NOT NULL REFERENCES users(id), event_id INTEGER NOT NULL REFERENCES events(id),
    status TEXT NOT NULL, total DOUBLE PRECISION NOT NULL, payment_ref TEXT,
    refund_amount DOUBLE PRECISION NOT NULL DEFAULT 0, refund_percent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, cancelled_at TEXT, cancel_reason TEXT);
CREATE TABLE IF NOT EXISTS tickets (
    id {PK}, booking_id INTEGER NOT NULL REFERENCES bookings(id), event_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL, user_id INTEGER NOT NULL, code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'valid', price DOUBLE PRECISION NOT NULL DEFAULT 0,
    issued_at TEXT NOT NULL, used_at TEXT, used_by INTEGER);
CREATE TABLE IF NOT EXISTS waitlist (
    id {PK}, event_id INTEGER NOT NULL, category_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
    offered_at TEXT, expires_at TEXT, booking_id INTEGER);
CREATE TABLE IF NOT EXISTS hire_requests (
    id {PK}, user_id INTEGER NOT NULL, venue_id INTEGER NOT NULL, start_time TEXT NOT NULL,
    end_time TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT '', guests INTEGER NOT NULL,
    status TEXT NOT NULL, price DOUBLE PRECISION NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, decided_by INTEGER);
CREATE TABLE IF NOT EXISTS calendar_slots (
    id {PK}, venue_id INTEGER NOT NULL, kind TEXT NOT NULL, ref_id INTEGER NOT NULL,
    start_time TEXT NOT NULL, end_time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications (
    id {PK}, user_id INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '', is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id {PK}, conversation_id TEXT NOT NULL, sender TEXT NOT NULL, receiver TEXT NOT NULL,
    performative TEXT NOT NULL, content TEXT NOT NULL, in_reply_to INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_state (
    agent TEXT NOT NULL, state_key TEXT NOT NULL, state_value TEXT NOT NULL,
    PRIMARY KEY (agent, state_key));
CREATE INDEX IF NOT EXISTS idx_tickets_event ON tickets(event_id);
CREATE INDEX IF NOT EXISTS idx_tickets_booking ON tickets(booking_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_waitlist_cat ON waitlist(category_id, status);
CREATE INDEX IF NOT EXISTS idx_slots_venue ON calendar_slots(venue_id, status)
"""


class Database:
    def __init__(self, url: str = "sqlite:///./eventsphere.db"):
        self.url = url
        self.is_pg = url.startswith(("postgres://", "postgresql://"))
        if self.is_pg:
            import psycopg2
            import psycopg2.extras

            self._pg = psycopg2
            self._pg_cursor = psycopg2.extras.RealDictCursor
        else:
            self.path = url.replace("sqlite:///", "", 1) if url.startswith("sqlite:///") else url
        self.init_schema()

    # -- connections ----------------------------------------------------------
    def _connect(self):
        if self.is_pg:
            return self._pg.connect(self.url, cursor_factory=self._pg_cursor)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _sql(self, sql: str) -> str:
        if not self.is_pg:
            return sql
        # psycopg2 treats every % as a placeholder marker, so literal % (e.g. LIKE 'scan:%') must be doubled
        return _PARAM.sub(r"%(\1)s", sql.replace("%", "%%"))

    def init_schema(self) -> None:
        pk = "SERIAL PRIMARY KEY" if self.is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        script = SCHEMA.replace("{PK}", pk)
        with self.tx() as t:
            for statement in script.split(";"):
                if statement.strip():
                    t.execute(statement)

    # -- API ------------------------------------------------------------------
    @contextmanager
    def tx(self):
        conn = self._connect()
        try:
            yield Tx(self, conn)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql, **params) -> int:
        with self.tx() as t:
            return t.execute(sql, **params)

    def insert(self, sql, **params) -> int:
        with self.tx() as t:
            return t.insert(sql, **params)

    def query(self, sql, **params) -> list[dict]:
        with self.tx() as t:
            return t.query(sql, **params)

    def one(self, sql, **params) -> dict | None:
        with self.tx() as t:
            return t.one(sql, **params)

    def scalar(self, sql, **params):
        with self.tx() as t:
            return t.scalar(sql, **params)


class Tx:
    def __init__(self, db: Database, conn):
        self.db, self.conn = db, conn

    def execute(self, sql, **params) -> int:
        cur = self.conn.cursor()
        cur.execute(self.db._sql(sql), params)
        return cur.rowcount

    def insert(self, sql, **params) -> int:
        cur = self.conn.cursor()
        if self.db.is_pg:
            cur.execute(self.db._sql(sql) + " RETURNING id", params)
            return cur.fetchone()["id"]
        cur.execute(sql, params)
        return cur.lastrowid

    def query(self, sql, **params) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(self.db._sql(sql), params)
        return [dict(r) for r in cur.fetchall()]

    def one(self, sql, **params) -> dict | None:
        rows = self.query(sql, **params)
        return rows[0] if rows else None

    def scalar(self, sql, **params):
        row = self.one(sql, **params)
        return next(iter(row.values())) if row else None
