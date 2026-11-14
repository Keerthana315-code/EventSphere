
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    venue_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    max_tickets: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3)
    category: Optional[str] = None
    venue_id: Optional[int] = Field(default=None, gt=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    max_tickets: Optional[int] = Field(default=None, gt=0)


class EventResponse(BaseModel):
    id: int
    title: str
    category: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    description: Optional[str]
    max_tickets: int
    tickets_sold: int
    status: str

    model_config = ConfigDict(from_attributes=True)
