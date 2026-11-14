
from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Event Management and Digital Ticketing Platform",
    version="1.0.0"
)


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
