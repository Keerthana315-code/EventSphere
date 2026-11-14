
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event
from app.models.private_hire import PrivateHire
from app.schemas.private_hire import PrivateHireCreate
from app.agents.message_bus import AgentMessage
from app.agents.venue_agent import VenueAgent

router = APIRouter(prefix="/private-hire", tags=["Private Hire"])

BUFFER_MINUTES = 60


@router.post("/")
def create_private_hire(
    hire_data: PrivateHireCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if hire_data.requested_end <= hire_data.requested_start:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    venue = db.query(Venue).filter(
        Venue.id == hire_data.venue_id,
        Venue.is_active == True
    ).first()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    if not venue.private_hire_enabled:
        raise HTTPException(
            status_code=400,
            detail="Private hire is not available for this venue"
        )

    if hire_data.expected_guests > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Guest count exceeds venue capacity"
        )

    # Ask VenueAgent to check event schedule and turnaround time.
    message = AgentMessage(
        sender="PrivateHireAPI",
        receiver="VenueAgent",
        performative="REQUEST",
        content={
            "action": "CHECK_EVENT_SCHEDULE",
            "venue_id": venue.id,
            "start_time": hire_data.requested_start.isoformat(),
            "end_time": hire_data.requested_end.isoformat()
        }
    )

    agent_result = VenueAgent.process_message(message, db)

    if agent_result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=409,
            detail="Venue is not available for the requested time"
        )

    # Also check existing accepted/pending private-hire requests.
    buffer = timedelta(minutes=BUFFER_MINUTES)

    existing_hire = db.query(PrivateHire).filter(
        PrivateHire.venue_id == venue.id,
        PrivateHire.status.in_(["accepted", "pending"]),
        PrivateHire.requested_start < hire_data.requested_end + buffer,
        PrivateHire.requested_end > hire_data.requested_start - buffer
    ).first()

    if existing_hire:
        raise HTTPException(
            status_code=409,
            detail="Venue has another private-hire request during this time"
        )

    duration_hours = (
        hire_data.requested_end - hire_data.requested_start
    ).total_seconds() / 3600

    estimated_price = duration_hours * venue.hourly_rate

    hire = PrivateHire(
        user_id=current_user.id,
        venue_id=venue.id,
        requested_start=hire_data.requested_start,
        requested_end=hire_data.requested_end,
        expected_guests=hire_data.expected_guests,
        description=hire_data.description,
        estimated_price=estimated_price,
        status="accepted"
    )

    db.add(hire)
    db.commit()
    db.refresh(hire)

    return {
        "message": "Private hire request accepted",
        "request": hire,
        "estimated_price": estimated_price,
        "currency": "LKR"
    }


@router.get("/my")
def get_my_private_hires(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(PrivateHire).filter(
        PrivateHire.user_id == current_user.id
    ).order_by(PrivateHire.created_at.desc()).all()


@router.get("/")
def get_all_private_hires(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return db.query(PrivateHire).order_by(
        PrivateHire.created_at.desc()
    ).all()


@router.patch("/{request_id}/cancel")
def cancel_private_hire(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    hire = db.query(PrivateHire).filter(
        PrivateHire.id == request_id
    ).first()

    if not hire:
        raise HTTPException(status_code=404, detail="Request not found")

    if current_user.role != "admin" and hire.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if hire.status != "accepted":
        raise HTTPException(status_code=400, detail="Request cannot be cancelled")

    hire.status = "cancelled"
    db.commit()

    return {
        "message": "Private hire cancelled",
        "request_id": hire.id,
        "status": hire.status
    }
