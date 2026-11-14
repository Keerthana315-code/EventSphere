
from datetime import timedelta

from app.agents.message_bus import AgentMessage
from app.models.event import Event


class VenueAgent:
    name = "VenueAgent"

    TURNAROUND_MINUTES = 60

    def process_message(self, message: AgentMessage, db):
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
            return self.validate_venue(message, message.content)

        if action == "CHECK_EVENT_SCHEDULE":
            return self.check_event_schedule(message, db)

        return AgentMessage(
            sender=self.name,
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": "Unknown action"},
            conversation_id=message.conversation_id
        )

    def validate_venue(self, message, content):
        capacity = content.get("capacity")
        hourly_rate = content.get("hourly_rate")

        if (
            not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or capacity <= 0
        ):
            reason = "Capacity must be a positive integer"

        elif (
            not isinstance(hourly_rate, (int, float))
            or isinstance(hourly_rate, bool)
            or hourly_rate < 0
        ):
            reason = "Hourly rate cannot be negative"

        else:
            return AgentMessage(
                sender=self.name,
                receiver=message.sender,
                performative="AGREE",
                content={"message": "Venue details validated"},
                conversation_id=message.conversation_id
            )

        return AgentMessage(
            sender=self.name,
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": reason},
            conversation_id=message.conversation_id
        )

    def check_event_schedule(self, message, db):
        content = message.content

        venue_id = content["venue_id"]
        start_time = content["start_time"]
        end_time = content["end_time"]
        exclude_event_id = content.get("exclude_event_id")

        buffer = timedelta(minutes=self.TURNAROUND_MINUTES)

        existing_events = db.query(Event).filter(
            Event.venue_id == venue_id,
            Event.status != "cancelled"
        ).all()

        for event in existing_events:
            if event.id == exclude_event_id:
                continue

            # Require a 60-minute gap between venue activities.
            overlaps = (
                start_time < event.end_time + buffer
                and end_time > event.start_time - buffer
            )

            if overlaps:
                return AgentMessage(
                    sender=self.name,
                    receiver=message.sender,
                    performative="REFUSE",
                    content={
                        "reason": "Venue schedule conflict",
                        "conflicting_event_id": event.id,
                        "conflicting_event": event.title,
                        "turnaround_buffer_minutes": self.TURNAROUND_MINUTES
                    },
                    conversation_id=message.conversation_id
                )

        return AgentMessage(
            sender=self.name,
            receiver=message.sender,
            performative="AGREE",
            content={
                "message": "Venue schedule is available",
                "turnaround_buffer_minutes": self.TURNAROUND_MINUTES
            },
            conversation_id=message.conversation_id
        )
