
from app.models.agent_log import AgentLog


def save_agent_message(db, message):

    log = AgentLog(
        sender=message.sender,
        receiver=message.receiver,
        performative=message.performative,
        content=str(message.content),
        conversation_id=message.conversation_id
    )

    db.add(log)
    db.commit()

    return log


def get_agent_logs(db):

    return (
        db.query(AgentLog)
        .order_by(AgentLog.id.desc())
        .all()
    )
