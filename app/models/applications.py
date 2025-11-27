from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class PartnerPending(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_name: str
    tax_office: str
    tax_number: str = Field(index=True)
    company_type: str
    contact_full_name: str
    tc_no_encrypted: str
    contact_email: str = Field(index=True)
    contact_phone: str = Field(index=True)
    total_vehicles: int
    fleet_type: str
    kvkk_consent: bool
    commercial_contract_approved: bool
    company_documents_image_url: Optional[str] = None
    document_status: str = Field(default="pending")
    missing_document_note: Optional[str] = None
    status: str = Field(default="pending", index=True)
    reject_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DriverPending(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    tc_no_encrypted: str = Field(index=True)
    birth_year: int
    email: str = Field(index=True)
    phone: str = Field(index=True)
    city: str
    driver_license_class: str
    driver_license_year: int
    criminal_record_confirmed: bool
    kvkk_consent: bool
    data_processing_consent: bool
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    plate_number: str = Field(index=True)
    fuel_type: str
    driver_license_image_url: Optional[str] = None
    vehicle_registration_image_url: Optional[str] = None
    document_status: str = Field(default="pending")
    missing_document_note: Optional[str] = None
    status: str = Field(default="pending", index=True)
    reject_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PartnerApplyRequest(SQLModel):
    company_name: str
    tax_office: str
    tax_number: str
    company_type: str
    contact_full_name: str
    tc_no: str
    contact_email: str
    contact_phone: str
    total_vehicles: int
    fleet_type: str
    kvkk_consent: bool
    commercial_contract_approved: bool
    company_documents_image_url: str


class DriverApplyRequest(SQLModel):
    full_name: str
    tc_no: str
    birth_year: int
    email: str
    phone: str
    city: str
    driver_license_class: str
    driver_license_year: int
    criminal_record_confirmed: bool
    kvkk_consent: bool
    data_processing_consent: bool
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    plate_number: str
    fuel_type: str
    driver_license_image_url: str
    vehicle_registration_image_url: str


class PartnerApplicationRead(SQLModel):
    id: int
    company_name: str
    tax_office: str
    tax_number: str
    company_type: str
    contact_full_name: str
    tc_no_masked: str
    contact_email: str
    contact_phone: str
    total_vehicles: int
    fleet_type: str
    kvkk_consent: bool
    commercial_contract_approved: bool
    company_documents_image_url: Optional[str] = None
    document_status: str
    missing_document_note: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime


class DriverApplicationRead(SQLModel):
    id: int
    full_name: str
    tc_no_masked: str
    birth_year: int
    email: str
    phone: str
    city: str
    driver_license_class: str
    driver_license_year: int
    criminal_record_confirmed: bool
    kvkk_consent: bool
    data_processing_consent: bool
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    plate_number: str
    fuel_type: str
    driver_license_image_url: Optional[str] = None
    vehicle_registration_image_url: Optional[str] = None
    document_status: str
    missing_document_note: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime
