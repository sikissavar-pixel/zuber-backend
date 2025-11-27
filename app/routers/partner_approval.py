from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
import logging

from ..database import get_session
from ..auth import require_role
from ..models.partner import Partner
from ..services.approval import ensure_user, activate_user_flags, send_approval_email, MailerError

router = APIRouter(prefix="/partners", tags=["partners"])
logger = logging.getLogger(__name__)


@router.patch("/{partner_id}/approve", dependencies=[Depends(require_role("admin"))])
def approve_partner(partner_id: int, session: Session = Depends(get_session)):
    partner = session.exec(select(Partner).where(Partner.id == partner_id)).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner bulunamadı")

    if getattr(partner, "approved", False):
        return {"success": True}

    safe_name = partner.name or "Partner"
    user, raw_password = ensure_user(session, partner.contact_email, safe_name, "partner")
    activate_user_flags(user)
    user.full_name = user.full_name or safe_name
    user.contact_phone = user.contact_phone or partner.contact_phone
    session.add(user)

    partner.active = True
    partner.approved = True
    session.add(partner)

    session.flush()
    try:
        send_approval_email(safe_name, partner.contact_email, raw_password)
    except MailerError as exc:
        session.rollback()
        logger.error("MAIL_FAILED %s", exc)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "MAIL_FAILED", "details": str(exc)},
        )

    session.commit()
    return {"success": True}
