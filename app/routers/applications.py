from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from ..database import get_session
from ..auth import require_role
from ..models.applications import PartnerPending, DriverPending
from ..models.partner import Partner
from ..models.user import User
from ..socket import sio
import asyncio
from ..services.approval import ensure_user, activate_user_flags, send_approval_email, MailerError


router = APIRouter(prefix="/api", tags=["applications"])


# Public apply endpoints
@router.post("/partners/apply", response_model=PartnerPending, status_code=status.HTTP_201_CREATED)
async def apply_partner(payload: PartnerPending, session: Session = Depends(get_session)):
    payload.status = "pending"
    session.add(payload)
    session.commit()
    session.refresh(payload)
    # Broadcast new application to admin room
    try:
        await sio.emit("new_application", {"type": "partner", "data": payload.model_dump()}, to="admin_room")
    except Exception:
        pass
    return payload


@router.post("/drivers/apply", response_model=DriverPending, status_code=status.HTTP_201_CREATED)
async def apply_driver(payload: DriverPending, session: Session = Depends(get_session)):
    payload.status = "pending"
    session.add(payload)
    session.commit()
    session.refresh(payload)
    try:
        await sio.emit("new_application", {"type": "driver", "data": payload.model_dump()}, to="admin_room")
    except Exception:
        pass
    return payload


# Admin-only listing endpoints
@router.get("/applications/partners", response_model=List[PartnerPending], dependencies=[Depends(require_role("admin"))])
def list_partner_applications(session: Session = Depends(get_session)):
    apps = session.exec(select(PartnerPending).where(PartnerPending.status == "pending")).all()
    return apps


@router.get("/applications/drivers", response_model=List[DriverPending], dependencies=[Depends(require_role("admin"))])
def list_driver_applications(session: Session = Depends(get_session)):
    apps = session.exec(select(DriverPending).where(DriverPending.status == "pending")).all()
    return apps


# Admin approval/rejection endpoints
@router.post("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(app_id: int, session: Session = Depends(get_session)):
    app = session.get(PartnerPending, app_id)
    if not app or app.status != "pending":
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

    app.status = "approved"
    session.add(app)

    dups = session.exec(select(PartnerPending).where(PartnerPending.contact_email == app.contact_email, PartnerPending.status == "pending", PartnerPending.id != app_id)).all()
    for dup in dups:
        dup.status = "approved"
        session.add(dup)

    session.flush()
    try:
        send_approval_email(safe_full_name, app.contact_email, temp_password)
    except MailerError:
        session.rollback()
        raise HTTPException(status_code=502, detail="Mail gönderilemedi, onay işlemi iptal edildi.")

    session.commit()

    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass

    return {"status": "ok", "email_sent": True, "message": "Şifre kullanıcıya mail olarak gönderildi."}


# Alias with PATCH method to support clients expecting PATCH
@router.patch("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner_patch(app_id: int, session: Session = Depends(get_session)):
    app = session.get(PartnerPending, app_id)
    if not app or app.status != "pending":
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

    app.status = "approved"
    session.add(app)

    dups = session.exec(select(PartnerPending).where(PartnerPending.contact_email == app.contact_email, PartnerPending.status == "pending", PartnerPending.id != app_id)).all()
    for dup in dups:
        dup.status = "approved"
        session.add(dup)

    session.flush()
    try:
        send_approval_email(safe_full_name, app.contact_email, temp_password)
    except MailerError:
        session.rollback()
        raise HTTPException(status_code=502, detail="Mail gönderilemedi, onay işlemi iptal edildi.")

    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass
    return {"status": "ok", "email_sent": True, "message": "Şifre kullanıcıya mail olarak gönderildi."}


@router.post("/applications/partners/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_partner(app_id: int, session: Session = Depends(get_session)):
    app = session.get(PartnerPending, app_id)
    if not app or app.status != "pending":
        raise HTTPException(status_code=404, detail="Application not found or not pending")
    app.status = "rejected"
    session.add(app)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "partner", "application_id": app_id, "status": "rejected"}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected"}


@router.post("/applications/drivers/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_driver(app_id: int, session: Session = Depends(get_session)):
    app = session.get(DriverPending, app_id)
    if not app or app.status != "pending":
        raise HTTPException(status_code=404, detail="Application not found or not pending")

    user, temp_password = ensure_user(session, app.email, app.full_name, "driver")
    activate_user_flags(user)
    user.full_name = app.full_name
    user.contact_phone = app.phone
    user.vehicle_plate = app.vehicle_plate
    app.status = "approved"
    session.add(user)
    session.add(app)
    session.flush()
    try:
        send_approval_email(app.full_name, app.email, temp_password)
    except MailerError:
        session.rollback()
        raise HTTPException(status_code=502, detail="Mail gönderilemedi, onay işlemi iptal edildi.")
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "driver", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("drivers_updated", {"user_id": user.id}))
    except Exception:
        pass
    return {"status": "ok", "email_sent": True, "message": "Şifre kullanıcıya mail olarak gönderildi."}


@router.post("/applications/drivers/{app_id}/reject", dependencies=[Depends(require_role("admin"))])
def reject_driver(app_id: int, session: Session = Depends(get_session)):
    app = session.get(DriverPending, app_id)
    if not app or app.status != "pending":
        raise HTTPException(status_code=404, detail="Application not found or not pending")
    app.status = "rejected"
    session.add(app)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_updated", {"type": "driver", "application_id": app_id, "status": "rejected"}, to="admin_room"))
    except Exception:
        pass
    return {"status": "rejected"}