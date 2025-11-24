from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, SQLModel
from ..database import get_session
from ..auth import get_current_user
from ..models.user import User
from ..models.reservation import Reservation, ReservationRead
from ..models.wallet import Wallet, WalletTransaction
from ..models.feedback import Feedback, FeedbackCreate
from ..socket import sio
import asyncio
from datetime import datetime

router = APIRouter(prefix="/api/driver", tags=["driver"])


def _get_or_create_wallet(session: Session, user_id: int) -> Wallet:
    w = session.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
    if not w:
        w = Wallet(user_id=user_id)
        session.add(w)
        session.commit()
        session.refresh(w)
    return w


class QRVerifyPayload(SQLModel):
    reservation_id: int


@router.get("/reservations", response_model=list[ReservationRead])
def driver_reservations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler erişebilir")
    rows = session.exec(
        select(Reservation)
        .where(Reservation.driver_id == current_user.id)
    ).all()
    # Optional: exclude cancelled to keep dashboard clean
    rows = [r for r in rows if r.status != "cancelled"]
    # Sort by pickup_time descending for recent-first
    rows.sort(key=lambda r: r.pickup_time, reverse=True)
    return [ReservationRead.model_validate(r) for r in rows]


@router.post("/qr/verify")
def qr_verify(
    payload: QRVerifyPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler doğrulama yapabilir")

    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    if r.driver_id and r.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyon size ait değil")

    # Demo amount and commission
    amount = r.total_amount or Decimal("350.00")

    # Partner or creator wallet holds the blocked funds
    payer_id = (r.partner_id or r.created_by_user_id)
    if not payer_id:
        payer_id = current_user.id  # fallback in demo
    w = _get_or_create_wallet(session, payer_id)

    # Ensure blocked_balance has enough to release (simulate pool)
    if w.blocked_balance < amount:
        # Move from available or top up demo balance
        missing = amount - w.blocked_balance
        w.available_balance = w.available_balance + missing
        w.blocked_balance = w.blocked_balance + missing
        session.add(w)
        session.commit()

    # Mark reservation completed & paid
    r.status = "completed"
    r.payment_status = "paid"
    r.total_amount = amount
    session.add(r)
    session.commit()
    session.refresh(r)

    # Commission and payout (using configured percent)
    from ..config import settings
    commission_rate = getattr(settings, "SYSTEM_FEE_PERCENT", 0.10)
    commission = (amount * Decimal(str(commission_rate))).quantize(Decimal("0.01"))
    payout = (amount - commission).quantize(Decimal("0.01"))

    # Reduce blocked balance and log transactions
    w.blocked_balance = w.blocked_balance - amount
    session.add(w)
    session.commit()
    tx_comm = WalletTransaction(user_id=payer_id, type="commission", amount=commission, description=f"Komisyon kesinti #{r.id}", related_reservation_id=r.id)
    tx_payout = WalletTransaction(user_id=payer_id, type="driver_payout", amount=payout, description=f"Sürücü ödemesi #{r.id}", related_reservation_id=r.id)
    session.add(tx_comm)
    session.add(tx_payout)
    session.commit()

    # Notify via socket for UI feedback
    try:
        payload = ReservationRead.model_validate(r).model_dump()
        # Emit asynchronously so sync endpoint doesn't cause coroutine-not-awaited
        sio.start_background_task(asyncio.run, sio.emit("booking_update", {"booking_id": r.id, "status": r.status, "payment_status": r.payment_status}))
        sio.start_background_task(asyncio.run, sio.emit("reservation_updated", payload))
        sio.start_background_task(asyncio.run, sio.emit("trip_completed", payload))
    except Exception:
        pass

    return {"status": "ok", "message": "Sürüş tamamlandı, QR doğrulandı.", "commission": str(commission), "payout": str(payout)}


@router.post("/feedback")
def submit_feedback(
    payload: FeedbackCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler geri bildirim gönderebilir")

    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    if r.driver_id and r.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyon size ait değil")

    fb = Feedback(reservation_id=payload.reservation_id, passenger_name=payload.passenger_name, rating=payload.rating, comment=payload.comment)
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return {"id": fb.id, "created_at": fb.created_at.isoformat()}


@router.get("/earnings")
def get_earnings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler erişebilir")

    # Dummy monthly earnings aligned with frontend chart
    monthly = [
        {"month": "Oca", "amount": 3200},
        {"month": "Şub", "amount": 2800},
        {"month": "Mar", "amount": 3500},
        {"month": "Nis", "amount": 4100},
        {"month": "May", "amount": 4600},
        {"month": "Haz", "amount": 4900},
        {"month": "Tem", "amount": 5200},
        {"month": "Ağu", "amount": 4800},
        {"month": "Eyl", "amount": 5300},
        {"month": "Eki", "amount": 5100},
        {"month": "Kas", "amount": 5400},
        {"month": "Ara", "amount": 5500},
    ]
    total = sum(m["amount"] for m in monthly)
    return {"total": total, "monthly": monthly}