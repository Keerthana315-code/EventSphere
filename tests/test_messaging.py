"""Message log, notifications, persistent state and the 'messages only' architecture rule."""
import json
import pathlib
import re

from app import repo
from app.agents.venue_agent import VenueAgent
from app.bus import Message, Performative


def test_one_booking_can_be_followed_across_agents_by_conversation_id(world):
    event = world.make_event()["event_id"]
    result = world.book(world.alice, event, 2)
    rows = world.db.query("SELECT * FROM messages WHERE conversation_id=:c ORDER BY id", c=result["conversation_id"])
    senders_and_receivers = {r["sender"] for r in rows} | {r["receiver"] for r in rows}
    assert {"BookingAgent", "TicketAgent", "ALL"} <= senders_and_receivers
    assert [r["performative"] for r in rows][0] == "REQUEST"
    assert "AGREE" in [r["performative"] for r in rows]
    assert all(json.loads(r["content"]) is not None for r in rows)


def test_every_refusal_carries_a_reason(world):
    event = world.make_event(quantity=1)["event_id"]
    world.book(world.alice, event)
    world.book(world.bob, event)
    for row in world.db.query("SELECT * FROM messages WHERE performative IN ('REFUSE','PROPOSE')"):
        assert json.loads(row["content"]).get("reason")


def test_notification_agent_tells_the_attendee_and_the_admin(world):
    event = world.make_event()["event_id"]
    world.book(world.alice, event)
    assert repo.unread_count(world.db, world.alice) == 1
    world.system.bus.request("test", "VenueAgent", "hire_request", user_id=world.alice, venue_id=world.venue,
                             start="2026-11-19 10:00:00", end="2026-11-19 12:00:00", guests=95, purpose="Big")
    assert repo.unread_count(world.db, world.admin) == 1  # hire_escalated -> admin


def test_agent_beliefs_persist_across_restart(world):
    event = world.make_event(quantity=2)["event_id"]
    world.book(world.alice, event, 2)
    fresh = VenueAgent(world.db, world.system.bus)
    assert fresh.get_state("slots_granted") == 1
    from app.agents.booking_agent import BookingAgent
    assert BookingAgent(world.db, world.system.bus).get_state("tickets_sold") == 2


def test_agents_never_import_or_call_each_other():
    """Rule 4.2.1: only the bus connects agents."""
    folder = pathlib.Path(__file__).parent.parent / "app" / "agents"
    names = {p.stem for p in folder.glob("*_agent.py")}
    for path in folder.glob("*_agent.py"):
        source = path.read_text()
        for other in names - {path.stem}:
            assert not re.search(rf"\b{other}\b", source.replace(other.replace("_agent", "").title() + "Agent", "")), (path, other)
        assert "from .booking_agent" not in source and "from .ticket_agent" not in source


def test_messages_are_structured_pydantic_models(world):
    msg = Message(sender="a", receiver="b", performative=Performative.REQUEST, content={"action": "x"})
    assert msg.conversation_id and msg.performative.value == "REQUEST"
    reply = msg.reply(Performative.REFUSE, reason="no")
    assert reply.conversation_id == msg.conversation_id and reply.sender == "b" and reply.receiver == "a"
