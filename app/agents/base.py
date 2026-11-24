"""Base class shared by all agents.

An agent owns: a goal, persistent beliefs (``agent_state`` table), and decision rules
(``on_<action>`` handlers). It only knows the message bus, never another agent object.
"""
import json
import threading

from ..bus import Message, Performative


class Agent:
    name = "Agent"
    goal = ""

    def __init__(self, db, bus):
        self.db = db
        self.bus = bus
        self._lock = threading.Lock()

    # ---- persistent beliefs (survive restarts because they live in the database) ----
    def get_state(self, key: str, default=None):
        row = self.db.one(
            "SELECT state_value FROM agent_state WHERE agent=:a AND state_key=:k", a=self.name, k=key
        )
        return json.loads(row["state_value"]) if row else default

    def set_state(self, key: str, value) -> None:
        self.db.execute(
            "INSERT INTO agent_state(agent, state_key, state_value) VALUES (:a, :k, :v) "
            "ON CONFLICT(agent, state_key) DO UPDATE SET state_value = excluded.state_value",
            a=self.name, k=key, v=json.dumps(value, default=str),
        )

    def incr(self, key: str, by: int = 1) -> int:
        with self._lock:
            value = int(self.get_state(key, 0)) + by
            self.set_state(key, value)
            return value

    # ---- message dispatch ----
    def handle(self, msg: Message) -> Message | None:
        content = msg.content
        if msg.performative == Performative.INFORM and "event" in content:
            handler = getattr(self, "on_event_" + str(content["event"]), None)
            if handler:
                handler(msg)  # reactive behaviour: no reply expected for broadcasts
            return None
        if msg.performative == Performative.REQUEST:
            handler = getattr(self, "on_" + str(content.get("action")), None)
            if handler is None:
                return msg.reply(Performative.FAILURE, reason=f"{self.name} does not understand action '{content.get('action')}'")
            return handler(msg)
        return None

    # ---- reply helpers ----
    def agree(self, msg: Message, **c) -> Message:
        return msg.reply(Performative.AGREE, **c)

    def refuse(self, msg: Message, reason: str, **c) -> Message:
        return msg.reply(Performative.REFUSE, reason=reason, **c)

    def propose(self, msg: Message, reason: str, options: list, **c) -> Message:
        return msg.reply(Performative.PROPOSE, reason=reason, options=options, **c)

    def inform(self, msg: Message, **c) -> Message:
        return msg.reply(Performative.INFORM, **c)

    def failure(self, msg: Message, reason: str, **c) -> Message:
        return msg.reply(Performative.FAILURE, reason=reason, **c)

    # ---- talking to other agents (always through the bus) ----
    def ask(self, receiver: str, action: str, conversation_id: str, **content) -> Message:
        return self.bus.request(self.name, receiver, action, conversation_id, **content)

    def announce(self, event: str, conversation_id: str, **content) -> None:
        self.bus.broadcast(self.name, event, conversation_id, **content)
