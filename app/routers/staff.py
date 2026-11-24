"""Gate staff scanner (staff and admin roles only)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .. import clock, services
from ..clock import fmt
from ..web import get_system, render, staff_required
from ..security import csrf_matches

router = APIRouter(prefix="/staff")


@router.get("/scan")
def scanner(request: Request, user=Depends(staff_required)):
    from datetime import timedelta

    db = get_system(request).db
    window_start = fmt(clock.now() - timedelta(days=1))
    events = db.query("SELECT id, title, start_time FROM events WHERE status='published' AND end_time >= :n ORDER BY start_time",
                      n=window_start)
    return render(request, "staff/scan.html", events=events)


@router.post("/scan")
async def scan(request: Request, user=Depends(staff_required)):
    if not csrf_matches(request.session.get("csrf"), request.headers.get("x-csrf-token")):
        return JSONResponse({"ok": False, "result": "error", "reason": "Security check failed. Reload the page."}, status_code=403)
    try:
        payload = await request.json()
        code, event_id = str(payload.get("code", "")).strip(), int(payload.get("event_id"))
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "result": "error", "reason": "Choose an event and scan or type a code."}, status_code=422)
    if not code:
        return JSONResponse({"ok": False, "result": "error", "reason": "Empty code."}, status_code=422)
    result = await run_in_threadpool(services.scan_ticket, get_system(request), user["id"], code, event_id)
    c = result["content"]
    return JSONResponse({"ok": result["ok"], "result": result["result"], "reason": result["reason"],
                         "holder": c.get("holder"), "category": c.get("category"), "event": c.get("event"),
                         "suspicious": c.get("suspicious", False)})
