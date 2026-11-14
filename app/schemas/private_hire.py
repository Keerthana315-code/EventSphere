
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class PrivateHireCreate(BaseModel):
    venue_id: int = Field(gt=0)
    requested_start: datetime
    requested_end: datetime
    expected_guests: int = Field(gt=0)
    description: Optional[str] = None


class PrivateHireResponse(BaseModel):
    id: int
    user_id: int
    venue_id: int
    requested_start: datetime
    requested_end: datetime
    expected_guests: int
    description: Optional[str]
    estimated_price: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
