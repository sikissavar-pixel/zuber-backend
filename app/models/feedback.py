from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reservation_id: int
    passenger_name: str
    rating: int
    comment: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackCreate(SQLModel):
    reservation_id: int
    passenger_name: str
    rating: int
    comment: str = Field(default="")