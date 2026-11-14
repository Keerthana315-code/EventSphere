
from sqlalchemy import Column, Integer, String, Text, Float, Boolean
from app.core.database import Base


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    location = Column(String(255), nullable=False)

    capacity = Column(Integer, nullable=False)

    description = Column(Text, nullable=True)

    image_url = Column(String(500), nullable=True)

    hourly_rate = Column(Float, nullable=False)

    private_hire_enabled = Column(Boolean, default=True)

    is_active = Column(Boolean, default=True)
