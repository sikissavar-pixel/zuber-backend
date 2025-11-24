from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from ..database import get_session
from ..auth import require_role, get_password_hash
from ..models.applications import PartnerPending, DriverPending
from ..models.partner import Partner
from ..models.user import User
from ..socket import sio
import asyncio
import random
import string


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

    # Create or update Partner as approved (idempotent)
    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.name = partner.name or app.name
        partner.contact_phone = partner.contact_phone or app.contact_phone
        partner.active = True
        partner.approved = True
        session.add(partner)
        session.commit()
        session.refresh(partner)
    else:
        partner = Partner(
            name=app.name,
            contact_email=app.contact_email,
            contact_phone=app.contact_phone,
            active=True,
            approved=True,
        )
        session.add(partner)
        session.commit()
        session.refresh(partner)

    # Create user for partner (role=partner) with a secure temporary password
    safe_full_name = app.contact_full_name or app.name or "Partner"
    temp_password = generate_temp_password(10)
    # Create or update user account for this partner
    user = session.exec(select(User).where(User.email == app.contact_email)).first()
    if user:
        user.full_name = user.full_name or safe_full_name
        user.role = "partner"
        user.password_hash = get_password_hash(temp_password)
        try:
            setattr(user, "must_change_password", True)
        except Exception:
            pass
        session.add(user)
    else:
        user = User(
            full_name=safe_full_name,
            email=app.contact_email,
            role="partner",
            password_hash=get_password_hash(temp_password),
            must_change_password=True,
        )
        session.add(user)
    app.status = "approved"
    session.add(app)
    session.commit()
    session.refresh(user)
    # Ensure any duplicate pending applications for same email are marked approved
    dups = session.exec(select(PartnerPending).where(PartnerPending.contact_email == app.contact_email, PartnerPending.status == "pending")).all()
    if dups:
        for d in dups:
            d.status = "approved"
            session.add(d)
        session.commit()
    # Return temporary password for admin to show once
    # Notify admin and partner client UIs
    try:
        # run emits in background from sync handler
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass
    return {"partner_id": partner.id, "user_id": user.id, "temporary_password": temp_password}


# Alias with PATCH method to support clients expecting PATCH
@router.patch("/applications/partners/{app_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner_patch(app_id: int, session: Session = Depends(get_session)):
    app = session.get(PartnerPending, app_id)
    if not app or app.status != "pending":
        raise HTTPException(status_code=404, detail="Application not found or not pending")

    # Create or update Partner as approved (idempotent)
    partner = session.exec(select(Partner).where(Partner.contact_email == app.contact_email)).first()
    if partner:
        partner.name = partner.name or app.name
        partner.contact_phone = partner.contact_phone or app.contact_phone
        partner.active = True
        partner.approved = True
        session.add(partner)
        session.commit()
        session.refresh(partner)
    else:
        partner = Partner(
            name=app.name,
            contact_email=app.contact_email,
            contact_phone=app.contact_phone,
            active=True,
            approved=True,
        )
        session.add(partner)
        session.commit()
        session.refresh(partner)

    # Create user for partner (role=partner) with a secure temporary password
    safe_full_name = app.contact_full_name or app.name or "Partner"
    temp_password = generate_temp_password(10)
    # Create or update user account for this partner
    user = session.exec(select(User).where(User.email == app.contact_email)).first()
    if user:
        user.full_name = user.full_name or safe_full_name
        user.role = "partner"
        user.password_hash = get_password_hash(temp_password)
        try:
            setattr(user, "must_change_password", True)
        except Exception:
            pass
        session.add(user)
    else:
        user = User(
            full_name=safe_full_name,
            email=app.contact_email,
            role="partner",
            password_hash=get_password_hash(temp_password),
            must_change_password=True,
        )
        session.add(user)
    app.status = "approved"
    session.add(app)
    session.commit()
    session.refresh(user)
    # Ensure any duplicate pending applications for same email are marked approved
    dups = session.exec(select(PartnerPending).where(PartnerPending.contact_email == app.contact_email, PartnerPending.status == "pending")).all()
    if dups:
        for d in dups:
            d.status = "approved"
            session.add(d)
        session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "partner", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner.id}))
    except Exception:
        pass
    return {"partner_id": partner.id, "user_id": user.id, "temporary_password": temp_password}


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

    # Create user for driver (role=driver) with a secure temporary password
    temp_password = generate_temp_password(10)
    user = User(
        full_name=app.full_name,
        email=app.email,
        role="driver",
        password_hash=get_password_hash(temp_password),
        must_change_password=True,
    )
    app.status = "approved"
    session.add(user)
    session.add(app)
    session.commit()
    session.refresh(user)
    try:
        sio.start_background_task(asyncio.run, sio.emit("application_approved", {"type": "driver", "application_id": app_id, "user_id": user.id}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("drivers_updated", {"user_id": user.id}))
    except Exception:
        pass
    return {"user_id": user.id, "temporary_password": temp_password}


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
def generate_temp_password(length: int = 10) -> str:
    # Ensure at least one uppercase, one digit, one symbol; prefix with Zb-
    prefix = "Zb-"
    symbols = "!@#$%^&*?"
    upper = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    symbol = random.choice(symbols)
    remaining_len = max(0, length - len(prefix) - 3)
    pool = string.ascii_letters + string.digits
    remaining = "".join(random.choice(pool) for _ in range(remaining_len))
    # Shuffle the components after the prefix
    tail_list = list(upper + digit + symbol + remaining)
    random.shuffle(tail_list)
    return prefix + "".join(tail_list)