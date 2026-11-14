
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)
from datetime import datetime
from app.core.database import Base


class PrivateHire(Base):
    __tablename__ = "private_hires"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    venue_id = Column(
        Integer,
        ForeignKey("venues.id"),
        nullable=False,
        index=True
    )

    requested_start = Column(DateTime, nullable=False)
    requested_end = Column(DateTime, nullable=False)

    expected_guests = Column(Integer, nullable=False)

    description = Column(Text, nullable=True)

    estimated_price = Column(Float, nullable=False, default=0.0)

    status = Column(
        String(30),
        nullable=False,
        default="pending"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
