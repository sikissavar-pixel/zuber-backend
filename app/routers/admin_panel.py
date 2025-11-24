from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..database import get_session
from ..auth import require_role
from ..models.partner import Partner
from ..models.user import User, UserRead
from ..models.applications import PartnerPending, DriverPending

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/partners", dependencies=[Depends(require_role("admin"))])
def admin_list_partners(session: Session = Depends(get_session)):
    return session.exec(select(Partner)).all()


@router.get("/drivers", response_model=list[UserRead], dependencies=[Depends(require_role("admin"))])
def admin_list_drivers(session: Session = Depends(get_session)):
    rows = session.exec(select(User).where(User.role == "driver")).all()
    return [UserRead.model_validate(u) for u in rows]


@router.get("/applications", dependencies=[Depends(require_role("admin"))])
def admin_list_applications(session: Session = Depends(get_session)):
    partner_apps = session.exec(select(PartnerPending)).all()
    driver_apps = session.exec(select(DriverPending)).all()
    return {"partners": partner_apps, "drivers": driver_apps}