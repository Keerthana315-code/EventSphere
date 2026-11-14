from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user

from app.models.user import User
from app.models.venue import Venue
from app.models.event import Event
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.private_hire import PrivateHire


router = APIRouter(
    prefix="/admin-api",
    tags=["Admin Dashboard"],
)


def check_admin(current_user):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_admin(current_user)

    return {
        "total_users": db.query(User).count(),
        "total_venues": db.query(Venue).count(),
        "total_events": db.query(Event).count(),
        "published_events": db.query(Event).filter(
            Event.status == "published"
        ).count(),
        "total_bookings": db.query(Booking).count(),
        "confirmed_bookings": db.query(Booking).filter(
            Booking.status == "confirmed"
        ).count(),
        "total_tickets": db.query(Ticket).count(),
        "checked_in_tickets": db.query(Ticket).filter(
            Ticket.status == "used"
        ).count(),
        "private_hire_requests": db.query(PrivateHire).count(),
    }


@router.get("/bookings")
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_admin(current_user)

    bookings = (
        db.query(Booking)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "id": booking.id,
            "user_id": booking.user_id,
            "event_id": booking.event_id,
            "ticket_type_id": booking.ticket_type_id,
            "quantity": booking.quantity,
            "total_amount": booking.total_amount,
            "status": booking.status,
            "payment_reference": booking.payment_reference,
            "created_at": booking.created_at,
        }
        for booking in bookings
    ]


@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_admin(current_user)

    users = db.query(User).order_by(User.id.desc()).all()

    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }
        for user in users
    ]