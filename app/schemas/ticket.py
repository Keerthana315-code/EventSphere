
from pydantic import BaseModel, Field, ConfigDict


class TicketTypeCreate(BaseModel):
    event_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=100)
    price: float = Field(ge=0)
    quantity: int = Field(gt=0)


class TicketTypeResponse(BaseModel):
    id: int
    event_id: int
    name: str
    price: float
    quantity: int
    sold: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    price: float | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
