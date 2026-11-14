
from app.agents.message_bus import AgentMessage


class VenueAgent:

    name = "VenueAgent"

    def process_message(self, message: AgentMessage):
        if message.receiver != self.name:
            return AgentMessage(
                sender=self.name,
                receiver=message.sender,
                performative="REFUSE",
                content={"reason": "Incorrect receiver"},
                conversation_id=message.conversation_id
            )

        if message.performative != "REQUEST":
            return AgentMessage(
                sender=self.name,
                receiver=message.sender,
                performative="REFUSE",
                content={"reason": "Unsupported performative"},
                conversation_id=message.conversation_id
            )

        action = message.content.get("action")

        if action == "VALIDATE_VENUE":
            return self.validate_venue(
                message.sender,
                message.content,
                message.conversation_id
            )

        return AgentMessage(
            sender=self.name,
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": "Unknown action"},
            conversation_id=message.conversation_id
        )

    def validate_venue(
        self,
        sender,
        content,
        conversation_id
    ):
        capacity = content.get("capacity")
        hourly_rate = content.get("hourly_rate")

        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
            return AgentMessage(
                sender=self.name,
                receiver=sender,
                performative="REFUSE",
                content={"reason": "Capacity must be a positive integer"},
                conversation_id=conversation_id
            )

        if (
            not isinstance(hourly_rate, (int, float))
            or isinstance(hourly_rate, bool)
            or hourly_rate < 0
        ):
            return AgentMessage(
                sender=self.name,
                receiver=sender,
                performative="REFUSE",
                content={"reason": "Hourly rate cannot be negative"},
                conversation_id=conversation_id
            )

        return AgentMessage(
            sender=self.name,
            receiver=sender,
            performative="AGREE",
            content={
                "message": "Venue details validated successfully"
            },
            conversation_id=conversation_id
        )
