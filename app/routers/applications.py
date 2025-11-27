from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import re

from ..database import get_session
from ..auth import require_role
from ..models.applications import (
    PartnerPending, DriverPending,
    PartnerApplyRequest, DriverApplyRequest,
    PartnerApplicationRead, DriverApplicationRead
)
from ..models.partner import Partner
from ..models.user import User
from ..socket import sio
import asyncio
from ..services.approval import ensure_user, activate_user_flags, send_approval_email, MailerError
from ..utils.encryption import encrypt_tc, decrypt_tc, mask_tc
from ..utils.tc_validation import validate_tc_no, validate_tax_number


router = APIRouter(prefix="/api", tags=["applications"])
logger = logging.getLogger(__name__)

_rate_limit_store = {}
_rate_limit_window = timedelta(minutes=5)
_rate_limit_max = 3


def _check_rate_limit(ip: str) -> bool:
    now = datetime.utcnow()
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    
    requests = _rate_limit_store[ip]
    requests = [r for r in requests if now - r < _rate_limit_window]
    _rate_limit_store[ip] = requests
    
    if len(requests) >= _rate_limit_max:
        return False
    
    requests.append(now)
    return True


def _validate_phone(phone: str) -> bool:
    phone = phone.strip()
    if phone.startswith("+90"):
        phone = phone[3:]
    if phone.startswith("0"):
        phone = phone[1:]
    return phone.isdigit() and len(phone) == 10


def _normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+90"):
        return phone
    if phone.startswith("0"):
        return "+90" + phone[1:]
    return "+90" + phone


def _validate_plate(plate: str) -> bool:
    pattern = r'^[0-9]{2}[A-Z]{1,3}[0-9]{2,4}$'
    return bool(re.match(pattern, plate.upper()))


@router.post("/partners/apply", status_code=status.HTTP_201_CREATED)
async def apply_partner(
    payload: PartnerApplyRequest,
    request: Request,
    session: Session = Depends(get_session)
):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    if not payload.kvkk_consent or not payload.commercial_contract_approved:
        raise HTTPException(status_code=400, detail="KVKK consent and commercial contract approval are mandatory")
    
    if not validate_tc_no(payload.tc_no):
        raise HTTPException(status_code=422, detail="Invalid TC Kimlik No")
    
    if not validate_tax_number(payload.tax_number):
        raise HTTPException(status_code=422, detail="Invalid tax number")
    
    if not _validate_phone(payload.contact_phone):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    if payload.total_vehicles < 1:
        raise HTTPException(status_code=400, detail="Total vehicles must be at least 1")
    
    if payload.company_type not in ["Şahıs", "Ltd", "AŞ"]:
        raise HTTPException(status_code=400, detail="Invalid company type")
    
    if payload.fleet_type not in ["VIP", "Standard", "Mixed"]:
        raise HTTPException(status_code=400, detail="Invalid fleet type")
    
    try:
        encrypted_tc = encrypt_tc(payload.tc_no)
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise HTTPException(status_code=500, detail="Encryption failed")
    
    existing_tc = session.exec(
        select(PartnerPending).where(PartnerPending.tc_no_encrypted == encrypted_tc)
    ).first()
    if existing_tc and existing_tc.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this TC number already exists")
    
    existing_email = session.exec(
        select(PartnerPending).where(PartnerPending.contact_email == payload.contact_email)
    ).first()
    if existing_email and existing_email.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this email already exists")
    
    existing_phone = session.exec(
        select(PartnerPending).where(PartnerPending.contact_phone == _normalize_phone(payload.contact_phone))
    ).first()
    if existing_phone and existing_phone.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this phone already exists")
    
    existing_tax = session.exec(
        select(PartnerPending).where(PartnerPending.tax_number == payload.tax_number)
    ).first()
    if existing_tax and existing_tax.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this tax number already exists")
    
    if not payload.company_documents_image_url:
        raise HTTPException(status_code=400, detail="Company documents image is required")
    
    app = PartnerPending(
        company_name=payload.company_name,
        tax_office=payload.tax_office,
        tax_number=payload.tax_number,
        company_type=payload.company_type,
        contact_full_name=payload.contact_full_name,
        tc_no_encrypted=encrypted_tc,
        contact_email=payload.contact_email,
        contact_phone=_normalize_phone(payload.contact_phone),
        total_vehicles=payload.total_vehicles,
        fleet_type=payload.fleet_type,
        kvkk_consent=payload.kvkk_consent,
        commercial_contract_approved=payload.commercial_contract_approved,
        company_documents_image_url=payload.company_documents_image_url,
        document_status="pending",
        status="pending"
    )
    session.add(app)
    session.flush()
    session.commit()
    session.refresh(app)
    
    logger.info(f"Partner application created: id={app.id}, email={payload.contact_email}, status={app.status}")
    
    try:
        await sio.emit("new_application", {"type": "partner", "application_id": app.id}, to="admin_room")
    except Exception:
        pass
    
    return {"success": True, "application_id": app.id}


@router.post("/drivers/apply", status_code=status.HTTP_201_CREATED)
async def apply_driver(
    payload: DriverApplyRequest,
    request: Request,
    session: Session = Depends(get_session)
):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    if not payload.kvkk_consent or not payload.data_processing_consent:
        raise HTTPException(status_code=400, detail="KVKK consent and data processing consent are mandatory")
    
    if len(payload.full_name) < 3:
        raise HTTPException(status_code=400, detail="Full name must be at least 3 characters")
    
    if not validate_tc_no(payload.tc_no):
        raise HTTPException(status_code=422, detail="Invalid TC Kimlik No")
    
    current_year = datetime.utcnow().year
    if payload.birth_year < 1955 or payload.birth_year > 2005:
        raise HTTPException(status_code=400, detail="Birth year must be between 1955 and 2005")
    
    if payload.driver_license_year > current_year:
        raise HTTPException(status_code=400, detail="Driver license year cannot be in the future")
    
    if payload.driver_license_class not in ["A", "B", "C", "D"]:
        raise HTTPException(status_code=400, detail="Invalid driver license class")
    
    if payload.vehicle_year < 2008:
        raise HTTPException(status_code=400, detail="Vehicle year must be 2008 or later")
    
    if payload.fuel_type not in ["diesel", "gasoline", "hybrid", "electric"]:
        raise HTTPException(status_code=400, detail="Invalid fuel type")
    
    if not _validate_phone(payload.phone):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    if not _validate_plate(payload.plate_number):
        raise HTTPException(status_code=400, detail="Invalid plate number format")
    
    try:
        encrypted_tc = encrypt_tc(payload.tc_no)
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise HTTPException(status_code=500, detail="Encryption failed")
    
    existing_tc = session.exec(
        select(DriverPending).where(DriverPending.tc_no_encrypted == encrypted_tc)
    ).first()
    if existing_tc:
        if existing_tc.status == "pending":
            raise HTTPException(status_code=409, detail="Application with this TC number already exists")
        if existing_tc.status == "rejected" and existing_tc.rejected_at:
            days_since_reject = (datetime.utcnow() - existing_tc.rejected_at).days
            if days_since_reject < 7:
                raise HTTPException(status_code=400, detail=f"Cannot reapply within 7 days of rejection. {7 - days_since_reject} days remaining.")
    
    existing_email = session.exec(
        select(DriverPending).where(DriverPending.email == payload.email)
    ).first()
    if existing_email and existing_email.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this email already exists")
    
    existing_phone = session.exec(
        select(DriverPending).where(DriverPending.phone == _normalize_phone(payload.phone))
    ).first()
    if existing_phone and existing_phone.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this phone already exists")
    
    existing_plate = session.exec(
        select(DriverPending).where(DriverPending.plate_number == payload.plate_number.upper())
    ).first()
    if existing_plate and existing_plate.status == "pending":
        raise HTTPException(status_code=409, detail="Application with this plate number already exists")
    
    if not payload.driver_license_image_url:
        raise HTTPException(status_code=400, detail="Driver license image is required")
    if not payload.vehicle_registration_image_url:
        raise HTTPException(status_code=400, detail="Vehicle registration image is required")
    
    app = DriverPending(
        full_name=payload.full_name,
        tc_no_encrypted=encrypted_tc,
        birth_year=payload.birth_year,
        email=payload.email,
        phone=_normalize_phone(payload.phone),
        city=payload.city,
        driver_license_class=payload.driver_license_class,
        driver_license_year=payload.driver_license_year,
        criminal_record_confirmed=payload.criminal_record_confirmed,
        kvkk_consent=payload.kvkk_consent,
        data_processing_consent=payload.data_processing_consent,
        vehicle_brand=payload.vehicle_brand,
        vehicle_model=payload.vehicle_model,
        vehicle_year=payload.vehicle_year,
        plate_number=payload.plate_number.upper(),
        fuel_type=payload.fuel_type,
        driver_license_image_url=payload.driver_license_image_url,
        vehicle_registration_image_url=payload.vehicle_registration_image_url,
        document_status="pending",
        status="pending"
    )
    session.add(app)
    session.flush()
    session.commit()
    session.refresh(app)
    
    logger.info(f"Driver application created: id={app.id}, email={payload.email}, status={app.status}")
    
    try:
        await sio.emit("new_application", {"type": "driver", "application_id": app.id}, to="admin_room")
    except Exception:
        pass
    
    return {"success": True, "application_id": app.id}


def _resolve_status_filter(status: Optional[str]) -> Optional[str]:
    if status is None or status == "":
        return "pending"
    status = status.lower()
    if status == "all":
        return None
    allowed = {"pending", "approved", "rejected"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")
    return status


def _update_user_flags(session: Session, email: str, *, is_active: bool, is_approved: bool):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return
    if hasattr(user, "is_active"):
        setattr(user, "is_active", is_active)
    if hasattr(user, "is_approved"):
        setattr(user, "is_approved", is_approved)
    session.add(user)


def _partner_app_to_read(app: PartnerPending) -> PartnerApplicationRead:
    try:
        tc_decrypted = decrypt_tc(app.tc_no_encrypted)
        tc_masked = mask_tc(tc_decrypted)
    except Exception:
        tc_masked = "******"
    
    return PartnerApplicationRead(
        id=app.id,
        company_name=app.company_name,
        tax_office=app.tax_office,
        tax_number=app.tax_number,
        company_type=app.company_type,
        contact_full_name=app.contact_full_name,
        tc_no_masked=tc_masked,
        contact_email=app.contact_email,
        contact_phone=app.contact_phone,
        total_vehicles=app.total_vehicles,
        fleet_type=app.fleet_type,
        kvkk_consent=app.kvkk_consent,
        commercial_contract_approved=app.commercial_contract_approved,
        company_documents_image_url=getattr(app, "company_documents_image_url", None),
        document_status=getattr(app, "document_status", "pending"),
        missing_document_note=getattr(app, "missing_document_note", None),
        status=app.status,
        reject_reason=app.reject_reason,
        rejected_at=app.rejected_at,
        created_at=app.created_at
    )


def _driver_app_to_read(app: DriverPending) -> DriverApplicationRead:
    try:
        tc_decrypted = decrypt_tc(app.tc_no_encrypted)
        tc_masked = mask_tc(tc_decrypted)
    except Exception:
        tc_masked = "******"
    
    return DriverApplicationRead(
        id=app.id,
        full_name=app.full_name,
        tc_no_masked=tc_masked,
        birth_year=app.birth_year,
        email=app.email,
        phone=app.phone,
        city=app.city,
        driver_license_class=app.driver_license_class,
        driver_license_year=app.driver_license_year,
        criminal_record_confirmed=app.criminal_record_confirmed,
        kvkk_consent=app.kvkk_consent,
        data_processing_consent=app.data_processing_consent,
        vehicle_brand=app.vehicle_brand,
        vehicle_model=app.vehicle_model,
        vehicle_year=app.vehicle_year,
        plate_number=app.plate_number,
        fuel_type=app.fuel_type,
        driver_license_image_url=getattr(app, "driver_license_image_url", None),
        vehicle_registration_image_url=getattr(app, "vehicle_registration_image_url", None),
        document_status=getattr(app, "document_status", "pending"),
        missing_document_note=getattr(app, "missing_document_note", None),
        status=app.status,
        reject_reason=app.reject_reason,
        rejected_at=app.rejected_at,
        created_at=app.created_at
    )


@router.get("/applications/partners", dependencies=[Depends(require_role("admin"))])
def list_partner_applications(
    status: Optional[str] = Query(default="pending"),
    session: Session = Depends(get_session),
):
    status_filter = _resolve_status_filter(status)
    stmt = select(PartnerPending)
    if status_filter:
        stmt = stmt.where(PartnerPending.status == status_filter)
    apps = session.exec(stmt.order_by(PartnerPending.id.desc())).all()
    return {"items": [_partner_app_to_read(app).model_dump() for app in apps]}


@router.get("/applications/drivers", dependencies=[Depends(require_role("admin"))])
def list_driver_applications(
    status: Optional[str] = Query(default="pending"),
    session: Session = Depends(get_session),
):
    try:
        status_filter = _resolve_status_filter(status)
        stmt = select(DriverPending)
        if status_filter:
            stmt = stmt.where(DriverPending.status == status_filter)
        apps = session.exec(stmt.order_by(DriverPending.id.desc())).all()
        result = {"items": [_driver_app_to_read(app).model_dump() for app in apps]}
        logger.info(f"List driver applications: status={status_filter}, count={len(result['items'])}")
        return result
    except Exception as e:
        logger.error(f"Error listing driver applications: {e}")
        return {"items": []}


@router.post("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(app_id: int, session: Session = Depends(get_session)):
    app = session.get(PartnerPending, app_id)
    if not app:
        return JSONResponse(status_code=404, content={"success": False, "error": "Application not found"})
    if app.status != "pending":
        return JSONResponse(status_code=400, content={"success": False, "error": "Application is not pending"})

    try:
        partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
        if partner:
            partner.name = partner.name or app.company_name
            partner.contact_phone = partner.contact_phone or app.contact_phone
        else:
            partner = Partner(
                name=app.company_name,
                contact_email=app.contact_email,
                contact_phone=app.contact_phone,
                active=True,
                approved=True,
            )
        partner.active = True
        partner.approved = True
        session.add(partner)

        safe_full_name = app.contact_full_name or app.company_name or "Partner"
        user, temp_password = ensure_user(session, app.contact_email, safe_full_name, "partner")
        activate_user_flags(user)
        user.full_name = user.full_name or safe_full_name
        user.contact_phone = user.contact_phone or app.contact_phone
        session.add(user)

        app.status = "approved"
        session.add(app)

        dups = session.exec(select(PartnerPending).where(PartnerPending.contact_email == app.contact_email, PartnerPending.status == "pending", PartnerPending.id != app_id)).all()
        for dup in dups:
            dup.status = "approved"
            session.add(dup)

        session.flush()
        send_approval_email(safe_full_name, app.contact_email, temp_password)
        session.commit()

        try:
            sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
            sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
        except Exception:
            pass

        return {"success": True}
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED")
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )
    except Exception as exc:
        session.rollback()
        logger.error("APPROVE_FAILED")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "APPROVE_FAILED", "details": str(exc)},
        )


@router.patch("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner_patch(app_id: int, session: Session = Depends(get_session)):
    return approve_partner(app_id, session)


@router.post("/applications/partners/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_partner(
    app_id: int,
    reason: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    app = session.get(PartnerPending, app_id)
    if not app:
        return JSONResponse(status_code=404, content={"success": False, "error": "Application not found"})
    if app.status != "pending":
        return JSONResponse(status_code=400, content={"success": False, "error": "Application is not pending"})
    
    app.status = "rejected"
    app.reject_reason = reason
    app.rejected_at = datetime.utcnow()
    session.add(app)
    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.active = False
        partner.approved = False
        session.add(partner)
    _update_user_flags(session, app.contact_email, is_active=False, is_approved=False)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "partner", "application_id": app_id, "status": "rejected"}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected", "success": True}


@router.post("/applications/drivers/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_driver(app_id: int, session: Session = Depends(get_session)):
    app = session.get(DriverPending, app_id)
    if not app:
        return JSONResponse(status_code=404, content={"success": False, "error": "Application not found"})
    if app.status != "pending":
        return JSONResponse(status_code=400, content={"success": False, "error": "Application is not pending"})

    try:
        user, temp_password = ensure_user(session, app.email, app.full_name, "driver")
        activate_user_flags(user)
        user.full_name = app.full_name
        user.contact_phone = app.phone
        user.vehicle_plate = app.plate_number
        app.status = "approved"
        session.add(user)
        session.add(app)
        session.flush()
        send_approval_email(app.full_name, app.email, temp_password)
        session.commit()
        try:
            sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "driver", "application_id": app_id, "user_id": user.id}, to="admin_room"))
            sio.start_background_task(asyncio.run, sio.emit("drivers_updated", {"user_id": user.id}))
        except Exception:
            pass
        return {"success": True}
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED")
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )
    except Exception as exc:
        session.rollback()
        logger.error("APPROVE_FAILED")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "APPROVE_FAILED", "details": str(exc)},
        )


@router.post("/applications/drivers/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_driver(
    app_id: int,
    reason: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    app = session.get(DriverPending, app_id)
    if not app:
        return JSONResponse(status_code=404, content={"success": False, "error": "Application not found"})
    if app.status != "pending":
        return JSONResponse(status_code=400, content={"success": False, "error": "Application is not pending"})
    
    app.status = "rejected"
    app.reject_reason = reason
    app.rejected_at = datetime.utcnow()
    session.add(app)
    _update_user_flags(session, app.email, is_active=False, is_approved=False)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "driver", "application_id": app_id, "status": "rejected"}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected", "success": True}
