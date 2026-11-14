
from datetime import datetime, timezone
from uuid import uuid4


class AgentMessage:
    def __init__(
        self,
        sender: str,
        receiver: str,
        performative: str,
        content: dict,
        conversation_id: str | None = None
    ):
        self.sender = sender
        self.receiver = receiver
        self.performative = performative
        self.content = content
        self.conversation_id = conversation_id or str(uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "performative": self.performative,
            "content": self.content,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp
        }
