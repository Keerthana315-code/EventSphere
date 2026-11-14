
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update
from datetime import datetime
from uuid import uuid4

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event
from app.models.ticket_type import TicketType
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.schemas.booking import BookingCreate
from app.agents.message_bus import AgentMessage
from app.agents.booking_agent import BookingAgent
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def check_booking_access(user, booking):
    if user.role != "admin" and booking.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/")
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(
        Event.id == booking_data.event_id
    ).first()

    if not event or event.status != "published":
        raise HTTPException(status_code=404, detail="Published event not found")

    ticket_type = db.query(TicketType).filter(
        TicketType.id == booking_data.ticket_type_id,
        TicketType.event_id == event.id,
        TicketType.is_active == True
    ).first()

    if not ticket_type:
        raise HTTPException(status_code=404, detail="Ticket type not found")

    message = AgentMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative="REQUEST",
        content={
            "action": "VALIDATE_BOOKING",
            "event_id": event.id,
            "ticket_type_id": ticket_type.id,
            "quantity": booking_data.quantity
        }
    )

    agent_result = BookingAgent.process_message(message, db)

    if agent_result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=agent_result.get("content", "Booking rejected")
        )

    total_amount = ticket_type.price * booking_data.quantity

    try:
        # Atomically reserve ticket-type quantity.
        stock_result = db.execute(
            update(TicketType)
            .where(
                TicketType.id == ticket_type.id,
                TicketType.is_active == True,
                TicketType.sold + booking_data.quantity <= TicketType.quantity
            )
            .values(sold=TicketType.sold + booking_data.quantity)
        )

        if stock_result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=400, detail="Not enough tickets available")

        # Atomically protect the overall event capacity too.
        capacity_result = db.execute(
            update(Event)
            .where(
                Event.id == event.id,
                Event.status == "published",
                Event.tickets_sold + booking_data.quantity <= Event.max_tickets
            )
            .values(tickets_sold=Event.tickets_sold + booking_data.quantity)
        )

        if capacity_result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=400, detail="Event capacity is full")

        payment = PaymentService.process_payment(total_amount)

        if not payment["success"]:
            db.rollback()
            raise HTTPException(status_code=400, detail="Payment failed")

        booking = Booking(
            user_id=current_user.id,
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            quantity=booking_data.quantity,
            total_amount=total_amount,
            status="confirmed",
            payment_reference=payment["payment_reference"]
        )

        db.add(booking)
        db.flush()

        # Generate one unique ticket code for each ticket.
        for _ in range(booking_data.quantity):
            ticket = Ticket(
                booking_id=booking.id,
                ticket_code=uuid4().hex,
                status="valid"
            )
            db.add(ticket)

        db.commit()
        db.refresh(booking)

        return {
            "message": "Booking successful",
            "booking_id": booking.id,
            "quantity": booking.quantity,
            "total_amount": booking.total_amount,
            "payment_reference": booking.payment_reference,
            "status": booking.status
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Booking could not be completed")


@router.get("/my")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).order_by(Booking.created_at.desc()).all()


@router.get("/{booking_id}")
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    check_booking_access(current_user, booking)
    return booking


@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(
        Booking.id == booking_id
    ).with_for_update().first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    check_booking_access(current_user, booking)

    if booking.status != "confirmed":
        raise HTTPException(status_code=400, detail="Booking cannot be cancelled")

    try:
        ticket_type = db.query(TicketType).filter(
            TicketType.id == booking.ticket_type_id
        ).first()

        event = db.query(Event).filter(
            Event.id == booking.event_id
        ).first()

        if not ticket_type or not event:
            raise HTTPException(status_code=404, detail="Booking data not found")

        ticket_type.sold = max(0, ticket_type.sold - booking.quantity)
        event.tickets_sold = max(0, event.tickets_sold - booking.quantity)

        tickets = db.query(Ticket).filter(
            Ticket.booking_id == booking.id
        ).all()

        for ticket in tickets:
            ticket.status = "cancelled"

        refund = PaymentService.refund_payment(
            booking.payment_reference
        )

        if not refund["success"]:
            raise HTTPException(status_code=400, detail="Refund failed")

        booking.status = "cancelled"

        db.commit()

        return {
            "message": "Booking cancelled successfully",
            "booking_id": booking.id,
            "refund": refund
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Cancellation failed")
