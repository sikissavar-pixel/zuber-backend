from typing import Optional
from decimal import Decimal
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlmodel import Session, select, SQLModel
from ..database import get_session
from ..models.payment import Payment
from ..models.reservation import Reservation, ReservationRead
from ..auth import get_current_user, require_role
from ..models.user import User
from ..config import settings
from ..socket import sio
from ..core.google_play_verify import verify_google_purchase

router = APIRouter(prefix="/api/payments", tags=["payments"])


class CreateIntentPayload(SQLModel):
    reservation_id: int
    amount: Decimal
    currency: Optional[str] = "usd"

class CorporatePayPayload(SQLModel):
    reservation_id: int
    method: str  # "invoice" | "credit"
    amount: Optional[Decimal] = None


@router.post("/create_intent")
def create_intent(
    payload: CreateIntentPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # Permission: Guest can pay for own reservation, Partner for ones they created, Admin allowed
    if current_user.role == "guest" and r.guest_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to pay for this reservation")
    if current_user.role == "partner" and r.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to pay for this reservation")
    # Admin allowed

    amount_cents = int(Decimal(str(payload.amount)) * 100)
    currency = (payload.currency or "usd").lower()

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            automatic_payment_methods={"enabled": True},
            metadata={"reservation_id": str(r.id), "user_id": str(current_user.id)},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {e}")

    # Persist payment draft
    r.total_amount = Decimal(str(payload.amount))
    r.payment_reference = intent.get("id")
    session.add(r)
    p = Payment(
        reservation_id=r.id,
        amount_cents=amount_cents,
        currency=currency.upper(),
        provider="stripe",
        status="pending",
    )
    session.add(p)
    session.commit()

    return {"client_secret": intent.get("client_secret"), "payment_intent_id": intent.get("id")}

@router.post("/corporate/pay")
def corporate_pay(
    payload: CorporatePayPayload,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    # Sadece rezervasyonu oluşturan partner veya admin işlem yapabilir
    if current_user.role == "partner" and r.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Yetkisiz işlem")
    if payload.method not in {"invoice", "credit"}:
        raise HTTPException(status_code=400, detail="Geçersiz kurumsal ödeme yöntemi")

    r.payment_status = "paid"
    r.total_amount = r.total_amount or (payload.amount or 0)
    r.payment_reference = f"corporate:{payload.method}:{r.id}"
    session.add(r)
    p = Payment(
        reservation_id=r.id,
        amount_cents=int((r.total_amount or 0) * 100),
        currency="USD",
        provider="corporate_" + payload.method,
        status="succeeded",
    )
    session.add(p)
    session.commit()
    background_tasks.add_task(sio.emit, "reservation_updated", ReservationRead.model_validate(r).model_dump())
    return {"ok": True}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    # Handle relevant events
    if event.get("type") == "payment_intent.succeeded":
        intent = event["data"]["object"]
        intent_id = intent.get("id")
        # Find reservation by payment_reference
        r = session.exec(select(Reservation).where(Reservation.payment_reference == intent_id)).first()
        if r:
            r.payment_status = "paid"
            session.add(r)
            # update payment row
            pay = session.exec(select(Payment).where(Payment.reservation_id == r.id, Payment.provider == "stripe")).first()
            if pay:
                pay.status = "succeeded"
                session.add(pay)
            session.commit()
            background_tasks.add_task(sio.emit, "reservation_updated", ReservationRead.model_validate(r).model_dump())
    elif event.get("type") == "payment_intent.payment_failed":
        intent = event["data"]["object"]
        intent_id = intent.get("id")
        r = session.exec(select(Reservation).where(Reservation.payment_reference == intent_id)).first()
        if r:
            # keep as unpaid
            pay = session.exec(select(Payment).where(Payment.reservation_id == r.id, Payment.provider == "stripe")).first()
            if pay:
                pay.status = "failed"
                session.add(pay)
            session.commit()

    return {"received": True}


@router.get("/me")
def my_payments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Filter payments based on the reservations visible to the user
    reservations = []
    if current_user.role == "guest":
        reservations = session.exec(select(Reservation).where(Reservation.guest_id == current_user.id)).all()
    elif current_user.role == "driver":
        reservations = session.exec(select(Reservation).where(Reservation.driver_id == current_user.id)).all()
    elif current_user.role == "partner":
        reservations = session.exec(select(Reservation).where(Reservation.created_by_user_id == current_user.id)).all()
    elif current_user.role == "admin":
        reservations = session.exec(select(Reservation)).all()

    res_ids = {r.id for r in reservations}
    rows = session.exec(select(Payment).where(Payment.reservation_id.in_(res_ids))).all() if res_ids else []
    return rows


class GooglePlayVerifyPayload(SQLModel):
    reservation_id: int
    product_id: str
    purchase_token: str


@router.post("/googleplay/verify")
def verify_googleplay(
    payload: GooglePlayVerifyPayload,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if current_user.role == "guest" and r.guest_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if current_user.role == "partner" and r.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    # Real verification via Google Play Developer API
    result = verify_google_purchase(product_id=payload.product_id, purchase_token=payload.purchase_token)

    r.payment_status = "paid"
    r.payment_reference = payload.purchase_token
    session.add(r)
    p = Payment(
        reservation_id=r.id,
        amount_cents=int(r.total_amount * 100) if r.total_amount else 0,
        currency="USD",
        provider="google_play",
        status="succeeded",
    )
    session.add(p)
    session.commit()
    background_tasks.add_task(sio.emit, "reservation_updated", ReservationRead.model_validate(r).model_dump())
    return {"ok": True, "google_result": result}