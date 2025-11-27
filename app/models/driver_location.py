from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class DriverLocation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    driver_id: int = Field(foreign_key="user.id", index=True, unique=True)
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class DriverLocationRead(SQLModel):
    driver_id: int
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    updated_at: datetime

