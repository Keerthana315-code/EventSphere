
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event

from app.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse
)

from app.routers.auth import get_current_user
from app.agents.message_bus import AgentMessage
from app.agents.venue_agent import VenueAgent


router = APIRouter(
    prefix="/events",
    tags=["Event Management"]
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


def validate_event_venue(
    venue_id,
    start_time,
    end_time,
    max_tickets,
    db,
    exclude_event_id=None
):
    venue = db.query(Venue).filter(
        Venue.id == venue_id,
        Venue.is_active == True
    ).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Active venue not found"
        )

    if max_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Ticket quantity exceeds venue capacity"
        )

    message = AgentMessage(
        sender="EventAPI",
        receiver="VenueAgent",
        performative="REQUEST",
        content={
            "action": "CHECK_EVENT_SCHEDULE",
            "venue_id": venue_id,
            "start_time": start_time,
            "end_time": end_time,
            "exclude_event_id": exclude_event_id
        }
    )

    response = venue_agent.process_message(message, db)

    if response.performative != "AGREE":
        raise HTTPException(
            status_code=409,
            detail=response.content
        )

    return venue


@router.post(
    "/",
    response_model=EventResponse,
    status_code=201
)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    validate_event_venue(
        event_data.venue_id,
        event_data.start_time,
        event_data.end_time,
        event_data.max_tickets,
        db
    )

    event = Event(
        **event_data.model_dump(),
        status="draft"
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get("/", response_model=list[EventResponse])
def get_published_events(
    db: Session = Depends(get_db)
):
    return db.query(Event).filter(
        Event.status == "published"
    ).order_by(Event.start_time).all()


@router.get("/manage/all", response_model=list[EventResponse])
def get_all_events(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    return db.query(Event).order_by(
        Event.start_time
    ).all()


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "published":
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return event


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft events can be edited"
        )

    update_data = event_data.model_dump(exclude_unset=True)

    new_values = {
        "venue_id": event.venue_id,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "max_tickets": event.max_tickets
    }
    new_values.update(update_data)

    if new_values["end_time"] <= new_values["start_time"]:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    validate_event_venue(
        new_values["venue_id"],
        new_values["start_time"],
        new_values["end_time"],
        new_values["max_tickets"],
        db,
        exclude_event_id=event.id
    )

    for key, value in update_data.items():
        setattr(event, key, value)

    db.commit()
    db.refresh(event)

    return event


@router.post("/{event_id}/publish", response_model=EventResponse)
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft events can be published"
        )

    validate_event_venue(
        event.venue_id,
        event.start_time,
        event.end_time,
        event.max_tickets,
        db,
        exclude_event_id=event.id
    )

    event.status = "published"

    db.commit()
    db.refresh(event)

    return event


@router.post("/{event_id}/cancel", response_model=EventResponse)
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled"
        )

    event.status = "cancelled"

    db.commit()
    db.refresh(event)

    return event
