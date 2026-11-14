
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import Event
from app.models.venue import Venue
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate, EventResponse

from app.routers.auth import get_current_user
from app.agents.message_bus import AgentMessage
from app.agents.venue_agent import VenueAgent


router = APIRouter(
    prefix="/events",
    tags=["Event Management"]
)

venue_agent = VenueAgent()


# --------------------------------------------------
# ADMIN AUTHENTICATION
# --------------------------------------------------

def require_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


# --------------------------------------------------
# VENUE AGENT VALIDATION
# --------------------------------------------------

def validate_event_venue(
    db: Session,
    venue_id: int,
    start_time,
    end_time,
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


# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------

@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED
)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):

    venue = validate_event_venue(
        db=db,
        venue_id=event_data.venue_id,
        start_time=event_data.start_time,
        end_time=event_data.end_time
    )

    if event_data.max_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Maximum tickets cannot exceed venue capacity"
        )

    event = Event(
        title=event_data.title,
        category=event_data.category,
        venue_id=event_data.venue_id,
        start_time=event_data.start_time,
        end_time=event_data.end_time,
        description=event_data.description,
        max_tickets=event_data.max_tickets,
        tickets_sold=0,
        status="draft"
    )

    db.add(event)

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event


# --------------------------------------------------
# GET ALL PUBLISHED EVENTS - PUBLIC
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[EventResponse]
)
def get_published_events(
    db: Session = Depends(get_db)
):

    events = db.query(Event).filter(
        Event.status == "published"
    ).all()

    return events


# --------------------------------------------------
# GET ALL EVENTS - ADMIN
# --------------------------------------------------

@router.get(
    "/manage/all",
    response_model=list[EventResponse]
)
def get_all_events(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):

    events = db.query(Event).order_by(
        Event.id.desc()
    ).all()

    return events


# --------------------------------------------------
# GET SINGLE PUBLISHED EVENT - PUBLIC
# --------------------------------------------------

@router.get(
    "/{event_id}",
    response_model=EventResponse
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.status == "published"
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return event


# --------------------------------------------------
# UPDATE DRAFT EVENT - ADMIN
# --------------------------------------------------

@router.put(
    "/{event_id}",
    response_model=EventResponse
)
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
            detail="Only draft events can be updated"
        )

    update_data = event_data.model_dump(exclude_unset=True)

    new_venue_id = update_data.get(
        "venue_id", event.venue_id
    )

    new_start_time = update_data.get(
        "start_time", event.start_time
    )

    new_end_time = update_data.get(
        "end_time", event.end_time
    )

    new_max_tickets = update_data.get(
        "max_tickets", event.max_tickets
    )

    if new_end_time <= new_start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    venue = validate_event_venue(
        db=db,
        venue_id=new_venue_id,
        start_time=new_start_time,
        end_time=new_end_time,
        exclude_event_id=event.id
    )

    if new_max_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Maximum tickets cannot exceed venue capacity"
        )

    if new_max_tickets < event.tickets_sold:
        raise HTTPException(
            status_code=400,
            detail="Maximum tickets cannot be less than tickets already sold"
        )

    for key, value in update_data.items():
        setattr(event, key, value)

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event


# --------------------------------------------------
# PUBLISH EVENT - ADMIN
# --------------------------------------------------

@router.post(
    "/{event_id}/publish",
    response_model=EventResponse
)
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

    if event.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Cancelled events cannot be published"
        )

    if event.status == "published":
        raise HTTPException(
            status_code=400,
            detail="Event is already published"
        )

    venue = validate_event_venue(
        db=db,
        venue_id=event.venue_id,
        start_time=event.start_time,
        end_time=event.end_time,
        exclude_event_id=event.id
    )

    if event.max_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Maximum tickets cannot exceed venue capacity"
        )

    event.status = "published"

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event


# --------------------------------------------------
# CANCEL EVENT - ADMIN
# --------------------------------------------------

@router.post(
    "/{event_id}/cancel",
    response_model=EventResponse
)
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

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event
