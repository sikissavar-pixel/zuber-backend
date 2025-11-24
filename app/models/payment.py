from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reservation_id: int = Field(index=True)
    amount_cents: int
    currency: str = "USD"
    provider: str  # stripe | google_play
    status: str = "pending"  # pending | succeeded | failed
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentCreate(SQLModel):
    reservation_id: int
    amount_cents: int
    currency: str = "USD"
    provider: str