"""EventSphere application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import Database
from .routers import admin, agents_api, attendee, auth, public, staff, verify
from .seed import seed_demo
from .system import Scheduler, System
from .web import BASE_DIR, RedirectTo, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(database_url: str | None = None, run_scheduler: bool = True, seed: bool | None = None) -> FastAPI:
    settings = get_settings()
    system = System(Database(database_url or settings.database_url), settings.hold_minutes)
    if settings.seed_demo if seed is None else seed:
        seed_demo(system, settings.demo_password)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = Scheduler(system, settings.sweep_seconds) if run_scheduler else None
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            scheduler.stop()

    app = FastAPI(title="EventSphere", description="Venue booking and ticketing run by cooperating agents.",
                  version="1.0.0", lifespan=lifespan)
    app.state.system = system
    app.state.settings = settings
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=settings.https_only,
                       same_site="lax", max_age=60 * 60 * 8, session_cookie="eventsphere_session")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    for module in (auth, public, attendee, admin, staff, agents_api, verify):
        app.include_router(module.router)

    @app.exception_handler(RedirectTo)
    async def _redirect(request: Request, exc: RedirectTo):
        return RedirectResponse(exc.url, status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        titles = {403: "Not allowed", 404: "Page not found", 405: "Method not allowed"}
        return render(request, "error.html", status_code=exc.status_code, code=exc.status_code,
                      title=titles.get(exc.status_code, "Something went wrong"), detail=exc.detail)

    return app
