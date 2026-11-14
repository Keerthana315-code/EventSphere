
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine

from app.models.user import User
from app.models.venue import Venue

from app.routers import auth, venues


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Event Management and Digital Ticketing Platform",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(venues.router)


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
