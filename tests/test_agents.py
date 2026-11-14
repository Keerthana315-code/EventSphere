
from app.agents.message_bus import AgentMessage


def test_agent_message_creation():
    message = AgentMessage(
        sender="BookingAgent",
        receiver="TicketAgent",
        performative="INFORM",
        content={"booking_id": 1}
    )

    assert message.sender == "BookingAgent"
    assert message.receiver == "TicketAgent"
    assert message.performative == "INFORM"


def test_agent_message_to_dict():
    message = AgentMessage(
        sender="VenueAgent",
        receiver="BookingAgent",
        performative="AGREE",
        content={"available": True}
    )

    result = message.to_dict()

    assert result["sender"] == "VenueAgent"
    assert result["receiver"] == "BookingAgent"
    assert result["performative"] == "AGREE"
    assert result["content"] == {"available": True}


def test_agent_message_has_conversation_id():
    message = AgentMessage(
        sender="TicketAgent",
        receiver="NotificationAgent",
        performative="INFORM",
        content={"ticket_id": 10}
    )

    assert message.conversation_id is not None
    assert len(message.conversation_id) > 0


def test_agent_message_timestamp():
    message = AgentMessage(
        sender="WaitlistAgent",
        receiver="BookingAgent",
        performative="REQUEST",
        content={}
    )

    assert message.timestamp is not None


def test_messages_have_unique_conversation_ids():
    first = AgentMessage("A", "B", "INFORM", {})
    second = AgentMessage("A", "B", "INFORM", {})

    assert first.conversation_id != second.conversation_id
