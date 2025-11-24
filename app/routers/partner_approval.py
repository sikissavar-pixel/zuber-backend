from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import string
import secrets

from ..database import get_session
from ..auth import get_password_hash, require_role
from ..models.partner import Partner
from ..models.user import User

router = APIRouter(prefix="/partners", tags=["partners"])

def generate_password(length: int = 10) -> str:
    """Generate a secure random password with at least 10 chars, mixed case and digits."""
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password) 
            and any(c.isupper() for c in password) 
            and any(c.isdigit() for c in password)):
            return password

@router.patch("/{partner_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(partner_id: int, session: Session = Depends(get_session)):
    partner = session.exec(select(Partner).where(Partner.id == partner_id)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner bulunamadı")

    # If already approved, just return status (idempotency)
    if getattr(partner, "approved", False):
        return {
            "status": "ok",
            "message": "Partner zaten onaylanmış",
            "email": partner.contact_email
        }

    # Generate secure password
    raw_password = generate_password()
    hashed = get_password_hash(raw_password)

    # Check if user exists
    user = session.exec(select(User).where(User.email == partner.contact_email)).first()
    
    if user:
        # Update existing user
        user.password_hash = hashed
        user.role = "partner"
        # Ensure force password change is set if the field exists
        if hasattr(user, "must_change_password"):
            user.must_change_password = True
        session.add(user)
    else:
        # Create new user
        user = User(
            full_name=partner.name,
            email=partner.contact_email,
            role="partner",
            password_hash=hashed,
            must_change_password=True
        )
        session.add(user)

    # Approve partner
    partner.approved = True
    session.add(partner)
    
    session.commit()
    session.refresh(partner)
    # session.refresh(user)

    return {
        "status": "ok",
        "email": partner.contact_email,
        "password": raw_password
    }