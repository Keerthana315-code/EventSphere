
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class BookingCreate(BaseModel):
    event_id: int = Field(gt=0)
    ticket_type_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=10)


class BookingResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    ticket_type_id: int
    quantity: int
    total_amount: float
    status: str
    payment_reference: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketResponse(BaseModel):
    id: int
    booking_id: int
    ticket_code: str
    status: str
    checked_in_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
