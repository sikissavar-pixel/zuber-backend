from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy import func
from datetime import datetime, timedelta
from ..database import get_session
from ..auth import require_role
from ..models.partner import Partner
from ..models.user import User, UserRead
from ..models.applications import PartnerPending, DriverPending
from ..models.reservation import Reservation
from ..models.payment import Payment
from ..models.driver_location import DriverLocation

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


@router.get("/summary", dependencies=[Depends(require_role("admin"))])
def admin_summary(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    total_users = session.exec(select(func.count(User.id))).one() or 0
    total_drivers = session.exec(select(func.count(User.id)).where(User.role == "driver")).one() or 0
    total_partners = session.exec(select(func.count(Partner.id))).one() or 0
    
    pending_partner_apps = session.exec(select(func.count(PartnerPending.id)).where(PartnerPending.status == "pending")).one() or 0
    pending_driver_apps = session.exec(select(func.count(DriverPending.id)).where(DriverPending.status == "pending")).one() or 0
    total_applications = pending_partner_apps + pending_driver_apps

    recent_locations = session.exec(
        select(DriverLocation).where(DriverLocation.updated_at >= now - timedelta(minutes=5))
    ).all()
    online_drivers = len(recent_locations)

    active_reservations = session.exec(
        select(func.count(Reservation.id)).where(
            Reservation.status.in_(["pending", "assigned", "in_progress"])
        )
    ).one() or 0

    daily_revenue_query = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= today_start
        )
    ).one() or 0
    daily_revenue = float(daily_revenue_query) / 100.0 if daily_revenue_query else 0.0

    weekly_revenue_query = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= week_start
        )
    ).one() or 0
    weekly_revenue = float(weekly_revenue_query) / 100.0 if weekly_revenue_query else 0.0

    monthly_revenue_query = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= month_start
        )
    ).one() or 0
    monthly_revenue = float(monthly_revenue_query) / 100.0 if monthly_revenue_query else 0.0

    return {
        "total_users": total_users,
        "total_drivers": total_drivers,
        "total_partners": total_partners,
        "total_applications": total_applications,
        "online_drivers": online_drivers,
        "active_reservations": active_reservations,
        "daily_revenue": daily_revenue,
        "weekly_revenue": weekly_revenue,
        "monthly_revenue": monthly_revenue,
    }
