
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=255)
    capacity: int = Field(gt=0)
    description: Optional[str] = None
    image_url: Optional[str] = None
    hourly_rate: float = Field(ge=0)
    private_hire_enabled: bool = True


class VenueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2)
    location: Optional[str] = None
    capacity: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    image_url: Optional[str] = None
    hourly_rate: Optional[float] = Field(default=None, ge=0)
    private_hire_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class VenueResponse(BaseModel):
    id: int
    name: str
    location: str
    capacity: int
    description: Optional[str]
    image_url: Optional[str]
    hourly_rate: float
    private_hire_enabled: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
