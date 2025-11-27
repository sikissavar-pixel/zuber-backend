from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional
from ..database import get_session
from ..auth import require_role
from ..models.payment import Payment
from ..models.wallet import WalletTransaction

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/summary", dependencies=[Depends(require_role("admin"))])
def finance_summary(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)
    year_start = month_start.replace(month=1)

    daily_revenue = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= today_start
        )
    ).one() or 0
    daily_revenue = float(daily_revenue) / 100.0

    weekly_revenue = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= week_start
        )
    ).one() or 0
    weekly_revenue = float(weekly_revenue) / 100.0

    monthly_revenue = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= month_start
        )
    ).one() or 0
    monthly_revenue = float(monthly_revenue) / 100.0

    yearly_revenue = session.exec(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded",
            Payment.created_at >= year_start
        )
    ).one() or 0
    yearly_revenue = float(yearly_revenue) / 100.0

    total_transactions = session.exec(
        select(func.count(Payment.id)).where(Payment.status == "succeeded")
    ).one() or 0

    return {
        "daily_revenue": daily_revenue,
        "weekly_revenue": weekly_revenue,
        "monthly_revenue": monthly_revenue,
        "yearly_revenue": yearly_revenue,
        "total_transactions": total_transactions,
    }


@router.get("/transactions", dependencies=[Depends(require_role("admin"))])
def finance_transactions(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    transactions = session.exec(
        select(Payment)
        .where(Payment.status == "succeeded")
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    result = []
    for tx in transactions:
        result.append({
            "id": tx.id,
            "amount": float(tx.amount_cents) / 100.0 if tx.amount_cents else 0.0,
            "status": tx.status,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
            "payment_reference": getattr(tx, "payment_reference", None),
        })

    return {"items": result, "total": len(result)}

