
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine

# Import all database models before create_all
from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event

from app.routers import auth, venues, events


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Event Management and Digital Ticketing Platform",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(events.router)


@app.get("/")
def home():
    return {
        "message": "Welcome to EventSphere",
        "application": settings.APP_NAME,
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
