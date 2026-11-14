
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text
from app.core.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)

    sender = Column(String(100), nullable=False)
    receiver = Column(String(100), nullable=False)

    performative = Column(String(50), nullable=False)

    content = Column(Text, nullable=True)

    conversation_id = Column(String(100), nullable=False)

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
