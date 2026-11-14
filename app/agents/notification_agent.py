
from datetime import datetime, timezone

from app.agents.message_bus import AgentMessage


class NotificationAgent:

    def __init__(self):
        self.notifications = []

    def process_message(self, message, db=None):

        content = message.content
        action = content.get("action")

        if action == "SEND_NOTIFICATION":

            user_id = content.get("user_id")
            notification_message = content.get("message")

            if not user_id or not notification_message:
                return self.refuse(
                    message,
                    "User ID and notification message are required"
                )

            notification = {
                "id": len(self.notifications) + 1,
                "user_id": user_id,
                "message": notification_message,
                "sender_agent": message.sender,
                "conversation_id": message.conversation_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_read": False
            }

            self.notifications.append(notification)

            return AgentMessage(
                sender="NotificationAgent",
                receiver=message.sender,
                performative="INFORM",
                content={
                    "message": "Notification created",
                    "notification": notification
                },
                conversation_id=message.conversation_id
            )

        if action == "GET_NOTIFICATIONS":

            user_id = content.get("user_id")

            user_notifications = [
                item for item in self.notifications
                if item["user_id"] == user_id
            ]

            return AgentMessage(
                sender="NotificationAgent",
                receiver=message.sender,
                performative="INFORM",
                content={
                    "notifications": user_notifications,
                    "count": len(user_notifications)
                },
                conversation_id=message.conversation_id
            )

        return self.refuse(message, "Unknown notification action")

    def refuse(self, message, reason):

        return AgentMessage(
            sender="NotificationAgent",
            receiver=message.sender,
            performative="REFUSE",
            content={"reason": reason},
            conversation_id=message.conversation_id
        )
