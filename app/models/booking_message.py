from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class BookingMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    booking_id: int
    sender_role: str  # "partner" | "driver"
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)