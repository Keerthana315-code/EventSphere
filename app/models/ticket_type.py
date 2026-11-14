
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint
from app.core.database import Base


class TicketType(Base):
    __tablename__ = "ticket_types"

    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_event_ticket_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False)
    sold = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
