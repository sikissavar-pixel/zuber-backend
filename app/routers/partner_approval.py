from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import secrets

from ..database import get_session
from ..auth import get_password_hash, require_role
from ..models.partner import Partner
from ..models.user import User

router = APIRouter(prefix="/partners", tags=["partners"])


@router.patch("/{partner_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(partner_id: int, session: Session = Depends(get_session)):
    partner = session.exec(select(Partner).where(Partner.id == partner_id)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner bulunamadı")

    # If already approved, return info without generating a new password
    if getattr(partner, "approved", False):
        return {"message": "Zaten onaylanmış", "email": partner.contact_email}

    # Generate a temporary password and ensure a User exists/updated for this partner
    generated_password = secrets.token_hex(4)
    hashed = get_password_hash(generated_password)

    user = session.exec(select(User).where(User.email == partner.contact_email)).first()
    if user:
        user.password_hash = hashed
        try:
            setattr(user, "must_change_password", True)
        except Exception:
            pass
        session.add(user)
    else:
        user = User(
            full_name=partner.name,
            email=partner.contact_email,
            role="partner",
            password_hash=hashed,
            must_change_password=True,
        )
        session.add(user)

    partner.approved = True
    session.add(partner)
    session.commit()
    session.refresh(partner)
    session.refresh(user)

    return {
        "message": "Partner başarıyla onaylandı",
        "email": partner.contact_email,
        "temporary_password": generated_password,
    }