
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.ticket import Ticket
from app.models.booking import Booking
from app.models.event import Event
from app.services.qr_service import QRService

router = APIRouter(prefix="/tickets", tags=["Tickets"])


class TicketScanRequest(BaseModel):
    ticket_code: str = Field(min_length=1)
    event_id: int = Field(gt=0)


@router.get("/my")
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bookings = db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).all()

    booking_ids = [booking.id for booking in bookings]

    if not booking_ids:
        return []

    return db.query(Ticket).filter(
        Ticket.booking_id.in_(booking_ids)
    ).all()


@router.get("/{ticket_id}/qr")
def get_ticket_qr(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    booking = db.query(Booking).filter(
        Booking.id == ticket.booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if current_user.role != "admin" and booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    qr_result = QRService.generate_qr(ticket.ticket_code)

    return qr_result


@router.post("/scan")
def scan_ticket(
    scan_data: TicketScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "gate_staff"]:
        raise HTTPException(
            status_code=403,
            detail="Only gate staff or admin can scan tickets"
        )

    ticket = db.query(Ticket).filter(
        Ticket.ticket_code == scan_data.ticket_code
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Invalid ticket code")

    booking = db.query(Booking).filter(
        Booking.id == ticket.booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.event_id != scan_data.event_id:
        raise HTTPException(
            status_code=400,
            detail="This ticket belongs to another event"
        )

    if booking.status != "confirmed":
        raise HTTPException(status_code=400, detail="Booking is not valid")

    event = db.query(Event).filter(
        Event.id == booking.event_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    now = datetime.now()

    if now < event.start_time or now > event.end_time:
        raise HTTPException(
            status_code=400,
            detail="Ticket scanning is outside the event time"
        )

    # Atomic update prevents the same ticket being admitted twice.
    result = db.query(Ticket).filter(
        Ticket.id == ticket.id,
        Ticket.status == "valid"
    ).update(
        {
            "status": "used",
            "checked_in_at": now
        },
        synchronize_session=False
    )

    if result != 1:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Ticket already used or cancelled"
        )

    db.commit()

    return {
        "message": "Ticket accepted",
        "ticket_id": ticket.id,
        "event_id": event.id,
        "status": "used",
        "checked_in_at": now
    }
