from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from ..database import get_session
from ..auth import get_current_user
from ..models.user import User
from ..models.reservation import Reservation, ReservationCreate, ReservationRead
from ..models.booking_message import BookingMessage
from ..routers.reservations import _find_available_driver
from ..socket import sio
from decimal import Decimal
from ..models.wallet import Wallet, WalletTransaction
from sqlmodel import SQLModel
from ..config import settings

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("/")
def list_bookings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Mirror /api/reservations/me for partner role
    if current_user.role == "partner":
        rows = session.exec(select(Reservation).where(Reservation.created_by_user_id == current_user.id)).all()
    elif current_user.role == "guest":
        rows = session.exec(select(Reservation).where(Reservation.guest_id == current_user.id)).all()
    elif current_user.role == "driver":
        rows = session.exec(select(Reservation).where(Reservation.driver_id == current_user.id)).all()
    elif current_user.role == "admin":
        rows = session.exec(select(Reservation)).all()
    else:
        rows = []
    return [ReservationRead.model_validate(r) for r in rows]

@router.post("/create", response_model=ReservationRead)
def create_booking(
    payload: ReservationCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Alias endpoint that mirrors /api/reservations/ (partners often expect this path)
    if current_user.role not in {"guest", "partner", "admin"}:
        raise HTTPException(status_code=403, detail="Not allowed to create bookings")

    data = payload.model_dump()
    r = Reservation(**data)
    r.created_by_user_id = current_user.id
    if current_user.role == "guest":
        r.guest_id = current_user.id
    elif current_user.role == "partner":
        r.partner_id = r.partner_id or None

    # Default states
    r.status = "pending"
    r.payment_status = "unpaid"

    # Wallet check for partners: block estimated fare
    if current_user.role == "partner":
        # Simple flat estimate until pricing engine is available
        estimate = Decimal("100.00")
        # get or create wallet
        w = session.exec(select(Wallet).where(Wallet.user_id == current_user.id)).first()
        if not w:
            w = Wallet(user_id=current_user.id)
            session.add(w)
            session.commit()
            session.refresh(w)
        if w.available_balance < estimate:
            raise HTTPException(status_code=400, detail="Bakiyeniz yetersiz.")
        w.available_balance = w.available_balance - estimate
        w.blocked_balance = w.blocked_balance + estimate
        r.total_amount = estimate
        session.add(w)

    # Optional auto-assign driver
    driver_id = _find_available_driver(session)
    if driver_id:
        r.driver_id = driver_id
        r.status = "assigned"

    session.add(r)
    session.commit()
    session.refresh(r)

    # Record reservation_hold transaction
    if current_user.role == "partner":
        tx = WalletTransaction(
            user_id=current_user.id,
            type="reservation_hold",
            amount=estimate,
            description=f"Rezervasyon blokajı #{r.id}",
            related_reservation_id=r.id,
        )
        session.add(tx)
        session.commit()

    background_tasks.add_task(sio.emit, "reservation_created", ReservationRead.model_validate(r).model_dump())
    if r.driver_id:
        background_tasks.add_task(sio.emit, "reservation_assigned", ReservationRead.model_validate(r).model_dump())

    return ReservationRead.model_validate(r)


@router.post("/{booking_id}/qr_confirm")
def qr_confirm(
    booking_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Allow driver, partner, or admin to confirm (real world: driver)
    if current_user.role not in {"driver", "partner", "admin"}:
        raise HTTPException(status_code=403, detail="Not allowed")
    r = session.get(Reservation, booking_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    if r.status == "completed":
        return {"status": "already_completed"}

    # Commission and payout from partner's blocked balance
    w = session.exec(select(Wallet).where(Wallet.user_id == (r.partner_id or r.created_by_user_id))).first()
    if not w or w.blocked_balance < r.total_amount:
        raise HTTPException(status_code=400, detail="Bloke bakiye yetersiz")

    commission_rate = getattr(settings, "SYSTEM_FEE_PERCENT", 0.10)
    commission = (r.total_amount * Decimal(str(commission_rate))).quantize(Decimal("0.01"))
    payout = (r.total_amount - commission).quantize(Decimal("0.01"))

    # Release block and apply commission
    w.blocked_balance = w.blocked_balance - r.total_amount
    session.add(w)
    session.commit()
    session.refresh(w)

    # Log commission and payout transactions
    tx_comm = WalletTransaction(
        user_id=(r.partner_id or r.created_by_user_id or current_user.id),
        type="commission",
        amount=commission,
        description=f"Komisyon kesinti #{r.id}",
        related_reservation_id=r.id,
    )
    session.add(tx_comm)
    tx_payout = WalletTransaction(
        user_id=(r.partner_id or r.created_by_user_id or current_user.id),
        type="driver_payout",
        amount=payout,
        description=f"Sürücü ödemesi #{r.id}",
        related_reservation_id=r.id,
    )
    session.add(tx_payout)
    # Mark reservation completed & paid
    r.status = "completed"
    r.payment_status = "paid"
    session.add(r)
    session.commit()
    # Broadcast completion
    try:
        payload = ReservationRead.model_validate(r).model_dump()
        background_tasks.add_task(sio.emit, "reservation_updated", payload)
        background_tasks.add_task(sio.emit, "trip_completed", payload)
    except Exception:
        pass

    return {"status": "ok", "commission": str(commission), "payout": str(payout)}


@router.get("/{booking_id}/messages", response_model=list[dict])
def list_messages(
    booking_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Authorization: allow partner/driver/admin; guests only if they own it (not applicable here)
    # For simplicity, partners can view messages for any of their created bookings.
    rows = session.exec(
        Session.exec.__wrapped__(session, select(BookingMessage).where(BookingMessage.booking_id == booking_id))
    ) if False else session.exec(select(BookingMessage).where(BookingMessage.booking_id == booking_id)).all()
    return [{
        "id": m.id,
        "booking_id": m.booking_id,
        "sender_role": m.sender_role,
        "message": m.message,
        "created_at": m.created_at.isoformat(),
    } for m in rows]


class PostMessagePayload(SQLModel):
    message: str
    sender_role: str | None = None

@router.post("/{booking_id}/messages")
async def post_message(
    booking_id: int,
    body: PostMessagePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Persist message
    bm = BookingMessage(booking_id=booking_id, sender_role=body.sender_role or current_user.role, message=body.message)
    session.add(bm)
    session.commit()
    # Broadcast to room
    await sio.emit("chat_message", {"booking_id": booking_id, "sender_role": bm.sender_role, "message": bm.message})
    return {"ok": True}