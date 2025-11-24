from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(index=True)
    password_hash: str
    role: str = Field(index=True)  # guest | driver | partner | admin
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Extended profile fields
    identity_number: Optional[str] = None
    contact_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    profile_image_url: Optional[str] = None
    driver_license_url: Optional[str] = None
    vehicle_image_url: Optional[str] = None
    # Security: force password change on first login when using temporary passwords
    must_change_password: bool = False

class UserCreate(SQLModel):
    full_name: str
    email: str
    password: str
    role: str

class UserLogin(SQLModel):
    email: str
    password: str

class UserRead(SQLModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime
    identity_number: Optional[str] = None
    contact_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    profile_image_url: Optional[str] = None
    driver_license_url: Optional[str] = None
    vehicle_image_url: Optional[str] = None
    # Expose flag to client to redirect to change-password
    must_change_password: Optional[bool] = None

class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    identity_number: Optional[str] = None
    contact_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    profile_image_url: Optional[str] = None
    driver_license_url: Optional[str] = None
    vehicle_image_url: Optional[str] = None