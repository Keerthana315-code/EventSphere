"""Part C: every agent has an HTTP inbox that accepts JSON messages.

Authentication: an admin session (with CSRF header) OR the X-Agent-Key header matching the
AGENT_API_KEY environment variable (disabled when the variable is empty).
"""
import hmac

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from ..bus import Message
from ..security import csrf_matches
from ..web import current_user, get_system

router = APIRouter(prefix="/agents", tags=["agents"])


def _authorised(request: Request) -> bool:
    key = request.app.state.settings.agent_api_key
    supplied = request.headers.get("x-agent-key", "")
    if key and hmac.compare_digest(key, supplied):
        return True
    user = current_user(request)
    return bool(user and user["role"] == "admin" and csrf_matches(request.session.get("csrf"), request.headers.get("x-csrf-token")))


@router.get("")
def list_agents(request: Request):
    """Public: names and goals of the agents (no private data)."""
    return [{"name": a.name, "goal": a.goal, "inbox": f"/agents/{a.name}/inbox"} for a in get_system(request).agents]


@router.post("/{name}/inbox")
async def inbox(name: str, request: Request):
    """Deliver one JSON message to an agent and return its reply (if any)."""
    if not _authorised(request):
        raise HTTPException(status_code=403, detail="Admin session or a valid X-Agent-Key header is required.")
    system = get_system(request)
    if name not in system.bus.agents:
        raise HTTPException(status_code=404, detail=f"No agent called '{name}'.")
    try:
        msg = Message(**(await request.json()))
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid message: {exc}")
    msg.receiver = name
    reply = await run_in_threadpool(system.bus.send, msg)
    return reply.model_dump(mode="json") if reply else {"status": "delivered"}
