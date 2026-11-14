
from uuid import uuid4

from app.agents.message_bus import AgentMessage
from app.models.ticket import Ticket


class TicketAgent:

    def process_message(self, message, db):

        content = message.content
        action = content.get("action")

        if action == "GENERATE_TICKET_CODE":

            code = str(uuid4())

            return AgentMessage(
                sender="TicketAgent",
                receiver=message.sender,
                performative="AGREE",
                content={
                    "ticket_code": code
                },
                conversation_id=message.conversation_id
            )

        if action == "VALIDATE_TICKET":

            ticket_code = content.get("ticket_code")

            ticket = db.query(Ticket).filter(
                Ticket.ticket_code == ticket_code
            ).first()

            if not ticket:
                return self.refuse(message, "Invalid ticket")

            if ticket.status != "valid":
                return self.refuse(
                    message,
                    "Ticket already used or cancelled"
                )

            return AgentMessage(
                sender="TicketAgent",
                receiver=message.sender,
                performative="AGREE",
                content={
                    "ticket_id": ticket.id,
                    "booking_id": ticket.booking_id,
                    "message": "Ticket is valid"
                },
                conversation_id=message.conversation_id
            )

        return self.refuse(message, "Unknown ticket action")

    def refuse(self, message, reason):

        return AgentMessage(
            sender="TicketAgent",
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": reason},
            conversation_id=message.conversation_id
        )
