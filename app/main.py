
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine

# Import all database models
from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event
from app.models.ticket_type import TicketType
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.private_hire import PrivateHire
from app.models.agent_log import AgentLog
from app.models.waitlist import WaitlistEntry
from app.models.notification import Notification

# Import all API routers
from app.routers import (
    auth,
    venues,
    events,
    ticket_types,
    bookings,
    tickets,
    private_hire,
    agent_logs,
    admin,
)


# --------------------------------------------------
# PROJECT DIRECTORIES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "EventSphere - Multi-Agent Event Management "
        "and Digital Ticketing Platform"
    ),
    version="1.0.0",
)


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR),
        check_dir=False,
    ),
    name="static",
)


# --------------------------------------------------
# HTML TEMPLATES
# --------------------------------------------------

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# --------------------------------------------------
# API ROUTERS
# --------------------------------------------------

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(events.router)
app.include_router(ticket_types.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(private_hire.router)
app.include_router(agent_logs.router)
app.include_router(admin.router)


# --------------------------------------------------
# FRONTEND PAGES
# --------------------------------------------------

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={},
    )


@app.get("/scanner")
def scanner_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={},
    )


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "application": "EventSphere",
        "version": "1.0.0",
    }


# --------------------------------------------------
# API INFORMATION
# --------------------------------------------------

@app.get("/api", tags=["System"])
def api_information():
    return {
        "application": "EventSphere",
        "description": "Multi-Agent Event Management Platform",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "frontend": "/",
        "admin_dashboard": "/admin",
        "ticket_scanner": "/scanner",
        "endpoints": {
            "authentication": "/auth",
            "venues": "/venues",
            "events": "/events",
            "ticket_types": "/ticket-types",
            "bookings": "/bookings",
            "tickets": "/tickets",
            "private_hire": "/private-hire",
            "agent_logs": "/agent-logs",
            "admin": "/admin-api",
        },
    }


# --------------------------------------------------
# ROOT INFORMATION
# --------------------------------------------------

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return {"message": "EventSphere"}
