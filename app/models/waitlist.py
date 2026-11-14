from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from app.core.database import Base


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "ticket_type_id",
            "user_id",
            name="uq_waitlist_user_event_ticket",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    ticket_type_id = Column(
        Integer,
        ForeignKey("ticket_types.id"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    requested_quantity = Column(Integer, nullable=False, default=1)

    status = Column(
        String(30),
        nullable=False,
        default="waiting",
    )

    offer_code = Column(String(100), unique=True, nullable=True)

    offered_until = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )