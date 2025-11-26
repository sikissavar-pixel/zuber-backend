from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    available_balance: Decimal = Field(default=Decimal("0.00"))
    blocked_balance: Decimal = Field(default=Decimal("0.00"))
    partner_balance: Decimal = Field(default=Decimal("0.00"))
    driver_balance: Decimal = Field(default=Decimal("0.00"))
    trip_pool: Decimal = Field(default=Decimal("0.00"))
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WalletTransaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    # topup | reservation_hold | commission | driver_payout | refund
    type: str
    amount: Decimal
    description: Optional[str] = None
    related_reservation_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WalletSummary(SQLModel):
    available_balance: Decimal
    blocked_balance: Decimal
    # Backend note placeholders for Istanbul wallet transfer logic
    # Renamed conceptual field: payment_type -> wallet_transfer
    # Dummy aggregates for reporting: partner_balance, driver_balance, trip_pool
    partner_balance: Decimal = Field(default=Decimal("0.00"))
    driver_balance: Decimal = Field(default=Decimal("0.00"))
    trip_pool: Decimal = Field(default=Decimal("0.00"))