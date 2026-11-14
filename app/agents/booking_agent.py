
from app.agents.message_bus import AgentMessage
from app.models.event import Event
from app.models.ticket_type import TicketType


class BookingAgent:

    MAX_TICKETS_PER_BOOKING = 10

    def process_message(self, message, db):

        content = message.content
        action = content.get("action")

        if action == "VALIDATE_BOOKING":

            event_id = content.get("event_id")
            ticket_type_id = content.get("ticket_type_id")
            quantity = content.get("quantity")

            event = db.query(Event).filter(
                Event.id == event_id
            ).first()

            if not event or event.status != "published":
                return self.refuse(message, "Event is not available")

            ticket_type = db.query(TicketType).filter(
                TicketType.id == ticket_type_id,
                TicketType.event_id == event_id,
                TicketType.is_active == True
            ).first()

            if not ticket_type:
                return self.refuse(message, "Ticket category not found")

            if not isinstance(quantity, int) or isinstance(quantity, bool):
                return self.refuse(message, "Invalid ticket quantity")

            if quantity <= 0:
                return self.refuse(message, "Quantity must be greater than zero")

            if quantity > self.MAX_TICKETS_PER_BOOKING:
                return self.refuse(
                    message,
                    "Maximum 10 tickets per booking"
                )

            available = ticket_type.quantity - ticket_type.sold

            if quantity > available:
                return self.refuse(
                    message,
                    "Not enough tickets available"
                )

            return AgentMessage(
                sender="BookingAgent",
                receiver=message.sender,
                performative="AGREE",
                content={
                    "message": "Booking request validated",
                    "available_tickets": available
                },
                conversation_id=message.conversation_id
            )

        return self.refuse(message, "Unknown booking action")

    def refuse(self, message, reason):

        return AgentMessage(
            sender="BookingAgent",
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": reason},
            conversation_id=message.conversation_id
        )
