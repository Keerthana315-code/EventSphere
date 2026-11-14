
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.agents.agent_logger import get_agent_logs

router = APIRouter(
    prefix="/agent-logs",
    tags=["Agent Logs"]
)


@router.get("/")
def read_agent_logs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    logs = get_agent_logs(db)

    return [
        {
            "id": log.id,
            "sender": log.sender,
            "receiver": log.receiver,
            "performative": log.performative,
            "content": log.content,
            "conversation_id": log.conversation_id,
            "timestamp": log.timestamp
        }
        for log in logs
    ]
