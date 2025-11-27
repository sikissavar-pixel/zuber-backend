from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, SQLModel
from sqlalchemy import or_
from datetime import datetime, timedelta
from ..database import get_session
from ..auth import get_current_user, require_role
from ..models.user import User
from ..models.reservation import Reservation, ReservationRead
from ..models.wallet import Wallet, WalletTransaction
from ..models.feedback import Feedback, FeedbackCreate
from ..models.driver_location import DriverLocation, DriverLocationRead
from ..socket import sio
import asyncio

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


class DriverLocationPayload(SQLModel):
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    accuracy: float | None = None


@router.get("/locations")
def get_driver_locations(
    session: Session = Depends(get_session),
    _: User = Depends(require_role("admin")),
):
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=5)
        locations = session.exec(
            select(DriverLocation).where(DriverLocation.updated_at >= cutoff)
        ).all()
        
        result = []
        for loc in locations:
            result.append({
                "driver_id": loc.driver_id,
                "lat": loc.latitude,
                "lng": loc.longitude,
                "status": "online"
            })
        
        return result
    except Exception:
        return []


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
    rows = [r for r in rows if r.status != "cancelled"]
    rows.sort(key=lambda r: r.pickup_time, reverse=True)
    return [ReservationRead.model_validate(r) for r in rows]


@router.get("/open-reservations", response_model=list[ReservationRead])
def open_reservations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler erişebilir")
    allowed_statuses = ("pending", "open_bid")
    rows = session.exec(
        select(Reservation)
        .where(Reservation.status.in_(allowed_statuses))
        .where(or_(Reservation.driver_id.is_(None), Reservation.driver_id == current_user.id))
        .order_by(Reservation.pickup_time)
    ).all()
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

    amount = r.total_amount or Decimal("350.00")

    payer_id = (r.partner_id or r.created_by_user_id)
    if not payer_id:
        payer_id = current_user.id
    w = _get_or_create_wallet(session, payer_id)

    if w.blocked_balance < amount:
        missing = amount - w.blocked_balance
        w.available_balance = w.available_balance + missing
        w.blocked_balance = w.blocked_balance + missing
        session.add(w)
        session.commit()

    r.status = "completed"
    r.payment_status = "paid"
    r.total_amount = amount
    session.add(r)
    session.commit()
    session.refresh(r)

    from ..config import settings
    commission_rate = getattr(settings, "SYSTEM_FEE_PERCENT", 0.10)
    commission = (amount * Decimal(str(commission_rate))).quantize(Decimal("0.01"))
    payout = (amount - commission).quantize(Decimal("0.01"))

    w.blocked_balance = w.blocked_balance - amount
    session.add(w)
    session.commit()
    tx_comm = WalletTransaction(user_id=payer_id, type="commission", amount=commission, description=f"Komisyon kesinti #{r.id}", related_reservation_id=r.id)
    tx_payout = WalletTransaction(user_id=payer_id, type="driver_payout", amount=payout, description=f"Sürücü ödemesi #{r.id}", related_reservation_id=r.id)
    session.add(tx_comm)
    session.add(tx_payout)
    session.commit()

    try:
        payload = ReservationRead.model_validate(r).model_dump()
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


@router.post("/location", response_model=DriverLocationRead)
def upsert_location(
    payload: DriverLocationPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler konum paylaşabilir")

    location = session.exec(select(DriverLocation).where(DriverLocation.driver_id == current_user.id)).first()
    if not location:
        location = DriverLocation(driver_id=current_user.id, latitude=payload.latitude, longitude=payload.longitude)
    location.latitude = payload.latitude
    location.longitude = payload.longitude
    location.heading = payload.heading
    location.speed = payload.speed
    location.accuracy = payload.accuracy
    location.updated_at = datetime.utcnow()
    session.add(location)
    session.commit()
    session.refresh(location)

    serialized = DriverLocationRead.model_validate(location).model_dump()
    broadcast_payload = {
        **serialized,
        "driverId": serialized["driver_id"],
        "lat": serialized["latitude"],
        "lng": serialized["longitude"],
        "updatedAt": serialized["updated_at"].isoformat(),
    }
    try:
        sio.start_background_task(asyncio.run, sio.emit("driver_location_update", broadcast_payload))
        sio.start_background_task(asyncio.run, sio.emit("driver:location:update", broadcast_payload))
    except Exception:
        pass
    return serialized


@router.get("/location/me", response_model=DriverLocationRead)
def get_my_location(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Sadece sürücüler bu veriye erişebilir")
    location = session.exec(select(DriverLocation).where(DriverLocation.driver_id == current_user.id)).first()
    if not location:
        location = DriverLocation(
            driver_id=current_user.id,
            latitude=41.0082,
            longitude=28.9784,
        )
        session.add(location)
        session.commit()
        session.refresh(location)
    return DriverLocationRead.model_validate(location)
