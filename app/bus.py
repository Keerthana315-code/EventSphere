"""Message bus: the ONLY way agents talk to each other.

Every message is a Pydantic model with sender, receiver, performative, content and a
conversation id. Every message is written to the ``messages`` table so one user action
can be traced across agents on the admin dashboard.
"""
import json
import logging
import uuid
from enum import Enum

from pydantic import BaseModel, Field

from . import clock

log = logging.getLogger("eventsphere.bus")


class Performative(str, Enum):
    REQUEST = "REQUEST"
    AGREE = "AGREE"
    REFUSE = "REFUSE"
    PROPOSE = "PROPOSE"
    INFORM = "INFORM"
    FAILURE = "FAILURE"


def new_conversation_id() -> str:
    return uuid.uuid4().hex[:12]


class Message(BaseModel):
    id: int | None = None
    sender: str
    receiver: str
    performative: Performative
    content: dict = Field(default_factory=dict)
    conversation_id: str = Field(default_factory=new_conversation_id)
    in_reply_to: int | None = None

    def reply(self, performative: Performative, **content) -> "Message":
        return Message(
            sender=self.receiver,
            receiver=self.sender,
            performative=performative,
            content=content,
            conversation_id=self.conversation_id,
            in_reply_to=self.id,
        )

    @property
    def ok(self) -> bool:
        return self.performative in (Performative.AGREE, Performative.INFORM)


class MessageBus:
    BROADCAST = "ALL"

    def __init__(self, db):
        self.db = db
        self.agents: dict = {}

    def register(self, agent) -> None:
        self.agents[agent.name] = agent

    def _log(self, msg: Message) -> None:
        msg.id = self.db.insert(
            "INSERT INTO messages(conversation_id, sender, receiver, performative, content, in_reply_to, created_at) "
            "VALUES (:c, :s, :r, :p, :j, :irt, :t)",
            c=msg.conversation_id, s=msg.sender, r=msg.receiver, p=msg.performative.value,
            j=json.dumps(msg.content, default=str), irt=msg.in_reply_to, t=clock.fmt(clock.now()),
        )

    def send(self, msg: Message) -> Message | None:
        """Deliver one message and return the receiver's reply (already logged)."""
        self._log(msg)
        agent = self.agents.get(msg.receiver)
        if agent is None:
            reply = msg.reply(Performative.FAILURE, reason=f"Unknown agent '{msg.receiver}'")
        else:
            try:
                reply = agent.handle(msg)
            except Exception as exc:  # an agent crash must never take the others down
                log.exception("%s crashed while handling %s", msg.receiver, msg.content.get("action"))
                reply = msg.reply(Performative.FAILURE, reason=f"{msg.receiver} failed: {exc}")
        if reply is not None:
            self._log(reply)
        return reply

    def request(self, sender: str, receiver: str, action: str, conversation_id: str | None = None, **content) -> Message:
        msg = Message(
            sender=sender, receiver=receiver, performative=Performative.REQUEST,
            content={"action": action, **content},
            conversation_id=conversation_id or new_conversation_id(),
        )
        return self.send(msg)

    def broadcast(self, sender: str, event: str, conversation_id: str | None = None, **content) -> Message:
        """INFORM every other agent. Agents that care react in ``on_event_<event>``."""
        msg = Message(
            sender=sender, receiver=self.BROADCAST, performative=Performative.INFORM,
            content={"event": event, **content},
            conversation_id=conversation_id or new_conversation_id(),
        )
        self._log(msg)
        for name, agent in list(self.agents.items()):
            if name == sender:
                continue
            try:
                agent.handle(msg)
            except Exception:
                log.exception("%s failed on broadcast %s", name, event)
        return msg
