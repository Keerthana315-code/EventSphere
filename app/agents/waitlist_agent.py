
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agents.message_bus import AgentMessage


class WaitlistAgent:

    HOLD_MINUTES = 10

    def __init__(self):
        self.waitlists = {}
        self.active_holds = {}

    def process_message(self, message, db=None):

        content = message.content
        action = content.get("action")

        if action == "JOIN_WAITLIST":

            event_id = content.get("event_id")
            user_id = content.get("user_id")

            if not event_id or not user_id:
                return self.refuse(message, "Event and user are required")

            event_waitlist = self.waitlists.setdefault(event_id, [])

            if any(item["user_id"] == user_id for item in event_waitlist):
                return self.refuse(message, "User already in waitlist")

            event_waitlist.append({
                "user_id": user_id,
                "joined_at": datetime.now(timezone.utc).isoformat()
            })

            return self.agree(
                message,
                {"message": "Successfully joined waitlist"}
            )

        if action == "OFFER_TICKET":

            event_id = content.get("event_id")

            event_waitlist = self.waitlists.get(event_id, [])

            if not event_waitlist:
                return self.refuse(message, "Waitlist is empty")

            next_user = event_waitlist.pop(0)

            hold_id = str(uuid4())

            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=self.HOLD_MINUTES
            )

            self.active_holds[hold_id] = {
                "event_id": event_id,
                "user_id": next_user["user_id"],
                "expires_at": expires_at
            }

            return self.agree(
                message,
                {
                    "hold_id": hold_id,
                    "user_id": next_user["user_id"],
                    "expires_at": expires_at.isoformat()
                }
            )

        if action == "CHECK_EXPIRED_HOLDS":

            now = datetime.now(timezone.utc)
            expired = []

            for hold_id, hold in list(self.active_holds.items()):

                if hold["expires_at"] <= now:
                    expired.append({
                        "hold_id": hold_id,
                        "event_id": hold["event_id"],
                        "user_id": hold["user_id"]
                    })

                    del self.active_holds[hold_id]

                    self.waitlists.setdefault(
                        hold["event_id"], []
                    ).append({
                        "user_id": hold["user_id"],
                        "joined_at": now.isoformat()
                    })

            return self.agree(
                message,
                {
                    "expired_holds": expired,
                    "count": len(expired)
                }
            )

        if action == "CONFIRM_HOLD":

            hold_id = content.get("hold_id")
            hold = self.active_holds.get(hold_id)

            if not hold:
                return self.refuse(message, "Hold not found or expired")

            if hold["expires_at"] <= datetime.now(timezone.utc):
                del self.active_holds[hold_id]
                return self.refuse(message, "Hold has expired")

            del self.active_holds[hold_id]

            return self.agree(
                message,
                {"message": "Waitlist hold confirmed"}
            )

        return self.refuse(message, "Unknown waitlist action")

    def agree(self, message, content):

        return AgentMessage(
            sender="WaitlistAgent",
            receiver=message.sender,
            performative="AGREE",
            content=content,
            conversation_id=message.conversation_id
        )

    def refuse(self, message, reason):

        return AgentMessage(
            sender="WaitlistAgent",
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": reason},
            conversation_id=message.conversation_id
        )
