from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..database import get_session
from ..models.partner import Partner, PartnerCreate
from sqlmodel import SQLModel
from ..auth import require_role, get_current_user, verify_password, get_password_hash
from ..socket import sio
import asyncio
from ..models.user import User

router = APIRouter(prefix="/api/partners", tags=["partners"])

@router.get("/")
def list_partners(session: Session = Depends(get_session)):
    return session.exec(select(Partner)).all()

@router.post("/", dependencies=[Depends(require_role("admin"))])
def create_partner(payload: PartnerCreate, session: Session = Depends(get_session)):
    p = Partner(**payload.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    try:
        # Emit in background task to avoid coroutine-not-awaited warnings from sync handlers
        # schedule the actual coroutine on the server loop using ensure_future
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": p.id}))
    except Exception:
        pass
    return p


class PartnerUpdatePayload(SQLModel):
    name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None

@router.put("/update")
def update_partner(
    payload: PartnerUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "partner":
        raise HTTPException(status_code=403, detail="Only partners can update their profile")
    # Link partner by contact_email (fallback) or name if email missing
    partner = session.exec(select(Partner).where(Partner.contact_email == current_user.email)).first()
    if not partner:
        # Fallback: try by name
        partner = session.exec(select(Partner).where(Partner.name == current_user.full_name)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner record not found")

    data = payload.model_dump()
    # Only update fields that were provided (non-None).
    # Previous implementation wrote None values into required columns and
    # caused NOT NULL constraint errors (e.g. name). Skip None values.
    for k, v in data.items():
        if v is None:
            continue
        setattr(partner, k, v)
    session.add(partner)
    session.commit()
    session.refresh(partner)
    return partner


class ChangePasswordPayload(SQLModel):
    current_password: str
    new_password: str

@router.post("/change-password")
def change_password(
    body: ChangePasswordPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "partner":
        raise HTTPException(status_code=403, detail="Only partners can change password")
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(body.new_password)
    current_user.must_change_password = False
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return {"ok": True}


@router.delete("/{partner_id}", dependencies=[Depends(require_role("admin"))])
def delete_partner(partner_id: int, session: Session = Depends(get_session)):
    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    session.delete(partner)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner_id, "deleted": True}, to="admin_room"))
    except Exception:
        pass
    return {"status": "deleted", "partner_id": partner_id}