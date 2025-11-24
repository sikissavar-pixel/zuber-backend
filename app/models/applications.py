from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class PartnerPending(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    contact_full_name: str
    contact_email: str
    contact_phone: str
    city: str
    description: Optional[str] = None
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DriverPending(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    email: str
    phone: str
    license_no: str
    vehicle_plate: str
    city: str
    description: Optional[str] = None
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)