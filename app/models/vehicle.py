from typing import Optional
from sqlmodel import SQLModel, Field

class Vehicle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plate: str = Field(index=True)
    model: str
    capacity: int = 4
    active: bool = True

class VehicleCreate(SQLModel):
    plate: str
    model: str
    capacity: int = 4