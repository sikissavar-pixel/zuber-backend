from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Partner(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    contact_email: str
    contact_phone: str | None = None
    active: bool = True
    approved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PartnerCreate(SQLModel):
    name: str
    contact_email: str
    contact_phone: str | None = None