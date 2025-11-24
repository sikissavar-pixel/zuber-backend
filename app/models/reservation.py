from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field


class Reservation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Actors
    guest_id: Optional[int] = None
    driver_id: Optional[int] = None
    partner_id: Optional[int] = None
    created_by_user_id: Optional[int] = None  # track creator for partner/guest

    # Details
    guest_name: Optional[str] = None  # when partner books on behalf of a guest
    pickup_location: str
    dropoff_location: str
    pickup_time: datetime

    # Status
    status: str = Field(default="pending")  # pending | assigned | in_progress | completed | cancelled
    payment_status: str = Field(default="unpaid")  # unpaid | paid
    total_amount: Decimal = Field(default=Decimal("0.00"))
    payment_reference: Optional[str] = None  # e.g., Stripe PaymentIntent ID or Google purchase token

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReservationCreate(SQLModel):
    pickup_location: str
    dropoff_location: str
    pickup_time: datetime
    guest_name: Optional[str] = None


class ReservationRead(SQLModel):
    id: int
    guest_id: Optional[int]
    driver_id: Optional[int]
    partner_id: Optional[int]
    created_by_user_id: Optional[int]
    guest_name: Optional[str]
    pickup_location: str
    dropoff_location: str
    pickup_time: datetime
    status: str
    payment_status: str
    total_amount: Decimal
    payment_reference: Optional[str]
    created_at: datetime