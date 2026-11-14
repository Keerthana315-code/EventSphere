
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import Event
from app.models.ticket_type import TicketType
from app.models.user import User
from app.schemas.ticket import (
    TicketTypeCreate,
    TicketTypeResponse,
    TicketTypeUpdate
)
from app.routers.auth import get_current_user


router = APIRouter(
    prefix="/ticket-types",
    tags=["Ticket Categories"]
)


def require_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user


@router.post("/", response_model=TicketTypeResponse, status_code=201)
def create_ticket_type(
    ticket_data: TicketTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    event = db.query(Event).filter(
        Event.id == ticket_data.event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "published":
        raise HTTPException(
            status_code=400,
            detail="Tickets can only be created for published events"
        )

    if ticket_data.quantity + event.tickets_sold > event.max_tickets:
        raise HTTPException(
            status_code=400,
            detail="Ticket quantity exceeds remaining event capacity"
        )

    existing_type = db.query(TicketType).filter(
        TicketType.event_id == ticket_data.event_id,
        TicketType.name == ticket_data.name
    ).first()

    if existing_type:
        raise HTTPException(
            status_code=400,
            detail="This ticket category already exists for this event"
        )

    ticket_type = TicketType(
        event_id=ticket_data.event_id,
        name=ticket_data.name.strip(),
        price=ticket_data.price,
        quantity=ticket_data.quantity,
        sold=0,
        is_active=True
    )

    try:
        db.add(ticket_type)
        db.commit()
        db.refresh(ticket_type)
    except Exception:
        db.rollback()
        raise

    return ticket_type


@router.get("/{event_id}", response_model=list[TicketTypeResponse])
def get_event_ticket_types(
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
            detail="Published event not found"
        )

    return db.query(TicketType).filter(
        TicketType.event_id == event_id,
        TicketType.is_active == True
    ).all()


@router.put("/{ticket_type_id}", response_model=TicketTypeResponse)
def update_ticket_type(
    ticket_type_id: int,
    update_data: TicketTypeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    ticket_type = db.query(TicketType).filter(
        TicketType.id == ticket_type_id
    ).first()

    if not ticket_type:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found"
        )

    data = update_data.model_dump(exclude_unset=True)

    new_quantity = data.get("quantity", ticket_type.quantity)

    if new_quantity < ticket_type.sold:
        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be less than tickets already sold"
        )

    if "name" in data:
        duplicate = db.query(TicketType).filter(
            TicketType.event_id == ticket_type.event_id,
            TicketType.name == data["name"].strip(),
            TicketType.id != ticket_type_id
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=400,
                detail="This ticket category name already exists"
            )

        data["name"] = data["name"].strip()

    for key, value in data.items():
        setattr(ticket_type, key, value)

    try:
        db.commit()
        db.refresh(ticket_type)
    except Exception:
        db.rollback()
        raise

    return ticket_type
