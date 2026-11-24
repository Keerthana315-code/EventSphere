"""Pydantic models that validate everything users type into forms."""
from pydantic import BaseModel, Field, field_validator, model_validator

from . import clock
from .rules import EVENT_CATEGORIES


def _check_datetime(value: str) -> str:
    clock.parse(value)  # raises ValueError -> shown as a validation message
    return value


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    password: str = Field(min_length=8, max_length=128)


class VenueIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=200)
    capacity: int = Field(gt=0, le=100000)
    description: str = Field(default="", max_length=1000)
    image_url: str = Field(default="", max_length=500)
    hourly_rate: float = Field(ge=0)
    open_for_hire: bool = False

    @field_validator("image_url")
    @classmethod
    def _url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return v


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    price: float = Field(ge=0)
    quantity: int = Field(gt=0, le=100000)


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    category: str
    venue_id: int
    start: str
    end: str
    description: str = Field(default="", max_length=2000)
    categories: list[CategoryIn] = Field(min_length=1)
    publish: bool = False

    _start = field_validator("start")(lambda cls, v: _check_datetime(v))
    _end = field_validator("end")(lambda cls, v: _check_datetime(v))

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        if v not in EVENT_CATEGORIES:
            raise ValueError("choose one of: " + ", ".join(EVENT_CATEGORIES))
        return v

    @model_validator(mode="after")
    def _order(self):
        if clock.parse(self.end) <= clock.parse(self.start):
            raise ValueError("end time must be after the start time")
        if clock.parse(self.start) <= clock.now():
            raise ValueError("start time must be in the future")
        return self


class HireIn(BaseModel):
    venue_id: int
    start: str
    end: str
    guests: int = Field(ge=1, le=100000)
    purpose: str = Field(default="", max_length=200)

    _start = field_validator("start")(lambda cls, v: _check_datetime(v))
    _end = field_validator("end")(lambda cls, v: _check_datetime(v))
