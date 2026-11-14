
from sqlalchemy import (
    Column, Integer, String, Text,
    DateTime, ForeignKey
)
from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)

    venue_id = Column(
        Integer,
        ForeignKey("venues.id"),
        nullable=False,
        index=True
    )

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    description = Column(Text, nullable=True)

    max_tickets = Column(Integer, nullable=False)
    tickets_sold = Column(Integer, default=0, nullable=False)

    status = Column(
        String(20),
        default="draft",
        nullable=False
    )
