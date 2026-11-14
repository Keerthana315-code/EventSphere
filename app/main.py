
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine

# Import all database models before create_all
from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event
from app.models.ticket_type import TicketType
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.private_hire import PrivateHire

# Import API routers
from app.routers import auth
from app.routers import venues
from app.routers import events
from app.routers import ticket_types
from app.routers import bookings
from app.routers import tickets
from app.routers import private_hire

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Event Management and Digital Ticketing Platform",
    version="1.0.0"
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Frontend static files and templates
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

templates = Jinja2Templates(directory="app/templates")


# Register API routers
app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(events.router)
app.include_router(ticket_types.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(private_hire.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/scanner")
def scanner_page(request: Request):
    return templates.TemplateResponse(
        "scanner.html",
        {"request": request}
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}
