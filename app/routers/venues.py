
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.venue import Venue
from app.models.user import User

from app.schemas.venue import (
    VenueCreate,
    VenueUpdate,
    VenueResponse
)

from app.routers.auth import get_current_user
from app.agents.message_bus import AgentMessage
from app.agents.venue_agent import VenueAgent


router = APIRouter(
    prefix="/venues",
    tags=["Venue Management"]
)

venue_agent = VenueAgent()


def require_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


@router.post("/", response_model=VenueResponse, status_code=201)
def create_venue(
    venue_data: VenueCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    message = AgentMessage(
        sender="VenueAPI",
        receiver="VenueAgent",
        performative="REQUEST",
        content={
            "action": "VALIDATE_VENUE",
            "capacity": venue_data.capacity,
            "hourly_rate": venue_data.hourly_rate
        }
    )

    response = venue_agent.process_message(message)

    if response.performative != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=response.content["reason"]
        )

    venue = Venue(**venue_data.model_dump())

    db.add(venue)
    db.commit()
    db.refresh(venue)

    return venue


@router.get("/", response_model=list[VenueResponse])
def get_venues(
    db: Session = Depends(get_db)
):
    return db.query(Venue).filter(
        Venue.is_active == True
    ).all()


@router.get("/{venue_id}", response_model=VenueResponse)
def get_venue(
    venue_id: int,
    db: Session = Depends(get_db)
):
    venue = db.query(Venue).filter(
        Venue.id == venue_id,
        Venue.is_active == True
    ).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    return venue


@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int,
    venue_data: VenueUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    venue = db.query(Venue).filter(
        Venue.id == venue_id
    ).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    update_data = venue_data.model_dump(exclude_unset=True)

    capacity = update_data.get("capacity", venue.capacity)
    hourly_rate = update_data.get("hourly_rate", venue.hourly_rate)

    message = AgentMessage(
        sender="VenueAPI",
        receiver="VenueAgent",
        performative="REQUEST",
        content={
            "action": "VALIDATE_VENUE",
            "capacity": capacity,
            "hourly_rate": hourly_rate
        }
    )

    response = venue_agent.process_message(message)

    if response.performative != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=response.content["reason"]
        )

    for key, value in update_data.items():
        setattr(venue, key, value)

    db.commit()
    db.refresh(venue)

    return venue


@router.delete("/{venue_id}")
def delete_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    venue = db.query(Venue).filter(
        Venue.id == venue_id
    ).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    venue.is_active = False

    db.commit()

    return {
        "message": "Venue deactivated successfully"
    }
