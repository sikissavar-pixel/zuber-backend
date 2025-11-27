from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from typing import List, Optional
import logging

from ..database import get_session
from ..auth import require_role
from ..models.applications import PartnerPending, DriverPending
from ..models.partner import Partner
from ..models.user import User
from ..socket import sio
import asyncio
from ..services.approval import ensure_user, activate_user_flags, send_approval_email, MailerError


router = APIRouter(prefix="/api", tags=["applications"])
logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
ALLOWED_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED}


# Public apply endpoints
@router.post("/partners/apply", response_model=PartnerPending, status_code=status.HTTP_201_CREATED)
async def apply_partner(payload: PartnerPending, session: Session = Depends(get_session)):
    payload.status = STATUS_PENDING
    session.add(payload)
    session.commit()
    session.refresh(payload)
    try:
        await sio.emit("new_application", {"type": "partner", "data": payload.model_dump()}, to="admin_room")
    except Exception:
        pass
    return payload


@router.post("/drivers/apply", response_model=DriverPending, status_code=status.HTTP_201_CREATED)
async def apply_driver(payload: DriverPending, session: Session = Depends(get_session)):
    payload.status = STATUS_PENDING
    session.add(payload)
    session.commit()
    session.refresh(payload)
    try:
        await sio.emit("new_application", {"type": "driver", "data": payload.model_dump()}, to="admin_room")
    except Exception:
        pass
    return payload


def _resolve_status_filter(status: Optional[str]) -> Optional[str]:
    if status is None or status == "":
        return STATUS_PENDING
    status = status.lower()
    if status == "all":
        return None
    if status not in ALLOWED_STATUSES:
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


# Admin-only listing endpoints
@router.get("/applications/partners", response_model=List[PartnerPending], dependencies=[Depends(require_role("admin"))])
def list_partner_applications(
    status: Optional[str] = Query(default=STATUS_PENDING),
    session: Session = Depends(get_session),
):
    status_filter = _resolve_status_filter(status)
    stmt = select(PartnerPending)
    if status_filter:
        stmt = stmt.where(PartnerPending.status == status_filter)
    apps = session.exec(stmt.order_by(PartnerPending.id.desc())).all()
    return apps


@router.get("/applications/drivers", response_model=List[DriverPending], dependencies=[Depends(require_role("admin"))])
def list_driver_applications(
    status: Optional[str] = Query(default=STATUS_PENDING),
    session: Session = Depends(get_session),
):
    status_filter = _resolve_status_filter(status)
    stmt = select(DriverPending)
    if status_filter:
        stmt = stmt.where(DriverPending.status == status_filter)
    apps = session.exec(stmt.order_by(DriverPending.id.desc())).all()
    return apps


# Admin approval/rejection endpoints
@router.post("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(app_id: int, session: Session = Depends(get_session)):
    app = session.exec(
        select(PartnerPending).where(PartnerPending.id == app_id, PartnerPending.status == STATUS_PENDING)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not pending")

    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.name = partner.name or app.name
        partner.contact_phone = partner.contact_phone or app.contact_phone
    else:
        partner = Partner(
            name=app.name,
            contact_email=app.contact_email,
            contact_phone=app.contact_phone,
            active=True,
            approved=True,
        )
    partner.active = True
    partner.approved = True
    session.add(partner)

    safe_full_name = app.contact_full_name or app.name or "Partner"
    user, temp_password = ensure_user(session, app.contact_email, safe_full_name, "partner")
    activate_user_flags(user)
    user.full_name = user.full_name or safe_full_name
    user.contact_phone = user.contact_phone or app.contact_phone
    session.add(user)

    app.status = STATUS_APPROVED
    session.add(app)

    dups = session.exec(
        select(PartnerPending).where(
            PartnerPending.contact_email == app.contact_email,
            PartnerPending.status == STATUS_PENDING,
            PartnerPending.id != app_id,
        )
    ).all()
    for dup in dups:
        dup.status = STATUS_APPROVED
        session.add(dup)

    session.flush()
    try:
        send_approval_email(safe_full_name, app.contact_email, temp_password)
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED %s", exc)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )

    session.commit()

    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass

    return {"success": True}


# Alias with PATCH method to support clients expecting PATCH
@router.patch("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner_patch(app_id: int, session: Session = Depends(get_session)):
    app = session.exec(
        select(PartnerPending).where(PartnerPending.id == app_id, PartnerPending.status == STATUS_PENDING)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not pending")

    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.name = partner.name or app.name
        partner.contact_phone = partner.contact_phone or app.contact_phone
    else:
        partner = Partner(
            name=app.name,
            contact_email=app.contact_email,
            contact_phone=app.contact_phone,
            active=True,
            approved=True,
        )
    partner.active = True
    partner.approved = True
    session.add(partner)

    safe_full_name = app.contact_full_name or app.name or "Partner"
    user, temp_password = ensure_user(session, app.contact_email, safe_full_name, "partner")
    activate_user_flags(user)
    user.full_name = user.full_name or safe_full_name
    user.contact_phone = user.contact_phone or app.contact_phone
    session.add(user)

    app.status = STATUS_APPROVED
    session.add(app)

    dups = session.exec(
        select(PartnerPending).where(
            PartnerPending.contact_email == app.contact_email,
            PartnerPending.status == STATUS_PENDING,
            PartnerPending.id != app_id,
        )
    ).all()
    for dup in dups:
        dup.status = STATUS_APPROVED
        session.add(dup)

    session.flush()
    try:
        send_approval_email(safe_full_name, app.contact_email, temp_password)
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED %s", exc)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )

    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass
    return {"success": True}


@router.post("/applications/partners/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_partner(app_id: int, session: Session = Depends(get_session)):
    app = session.exec(
        select(PartnerPending).where(PartnerPending.id == app_id, PartnerPending.status == STATUS_PENDING)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not pending")
    app.status = STATUS_REJECTED
    session.add(app)
    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.active = False
        partner.approved = False
        session.add(partner)
    _update_user_flags(session, app.contact_email, is_active=False, is_approved=False)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "partner", "application_id": app_id, "status": STATUS_REJECTED}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected"}


@router.post("/applications/drivers/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_driver(app_id: int, session: Session = Depends(get_session)):
    app = session.exec(
        select(DriverPending).where(DriverPending.id == app_id, DriverPending.status == STATUS_PENDING)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not pending")

    user, temp_password = ensure_user(session, app.email, app.full_name, "driver")
    activate_user_flags(user)
    user.full_name = app.full_name
    user.contact_phone = app.phone
    user.vehicle_plate = app.vehicle_plate
    app.status = STATUS_APPROVED
    session.add(user)
    session.add(app)
    session.flush()
    try:
        send_approval_email(app.full_name, app.email, temp_password)
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED %s", exc)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "driver", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("drivers_updated", {"user_id": user.id}))
    except Exception:
        pass
    return {"success": True}


@router.post("/applications/drivers/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_driver(app_id: int, session: Session = Depends(get_session)):
    app = session.exec(
        select(DriverPending).where(DriverPending.id == app_id, DriverPending.status == STATUS_PENDING)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not pending")
    app.status = STATUS_REJECTED
    session.add(app)
    _update_user_flags(session, app.email, is_active=False, is_approved=False)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "driver", "application_id": app_id, "status": STATUS_REJECTED}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected"}