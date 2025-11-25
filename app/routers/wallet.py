from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, SQLModel
from ..database import get_session
from ..auth import get_current_user
from ..models.user import User
from ..models.wallet import Wallet, WalletTransaction, WalletSummary
from ..models.reservation import Reservation
import os
from datetime import datetime

router = APIRouter(tags=["Wallet"])


def _get_or_create_wallet(session: Session, user_id: int) -> Wallet:
    w = session.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
    if not w:
        w = Wallet(user_id=user_id)
        session.add(w)
        session.commit()
        session.refresh(w)
    return w


@router.get("/me")
def get_my_wallet(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    w = _get_or_create_wallet(session, current_user.id)
    txs = session.exec(
        select(WalletTransaction)
        .where(WalletTransaction.user_id == current_user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(10)
    ).all()
    return {
        "summary": WalletSummary(available_balance=w.available_balance, blocked_balance=w.blocked_balance).model_dump(),
        "transactions": [
            {
                "id": t.id,
                "date": t.created_at.isoformat(),
                "type": t.type,
                "amount": str(t.amount),
                "description": t.description,
            }
            for t in txs
        ],
    }

# Spec-compliant aliases
@router.get("")
def get_wallet_balance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    w = _get_or_create_wallet(session, current_user.id)
    return WalletSummary(available_balance=w.available_balance, blocked_balance=w.blocked_balance)

@router.get("/transactions")
def list_transactions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    txs = session.exec(
        select(WalletTransaction)
        .where(WalletTransaction.user_id == current_user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": t.id,
            "date": t.created_at.isoformat(),
            "type": t.type,
            "amount": str(t.amount),
            "description": t.description,
        }
        for t in txs
    ]


class TopupPayload(SQLModel):
    amount: Decimal
    method: str  # Shopier | Iyzico | card


@router.post("/topup")
def topup_wallet(
    payload: TopupPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"partner", "admin"}:
        raise HTTPException(status_code=403, detail="Topup not allowed")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Geçerli bir tutar girin")

    w = _get_or_create_wallet(session, current_user.id)
    w.available_balance = w.available_balance + payload.amount
    session.add(w)
    session.commit()
    session.refresh(w)

    tx = WalletTransaction(
        user_id=current_user.id,
        type="topup",
        amount=payload.amount,
        description=f"Topup via {payload.method}",
    )
    session.add(tx)
    session.commit()

    # Security audit log
    try:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(base_dir, exist_ok=True)
        log_path = os.path.join(base_dir, "wallet.log")
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.utcnow().isoformat()
            f.write(f"{ts} | wallet_topup | user_id={current_user.id} | amount={payload.amount} | method={payload.method}\n")
    except Exception:
        pass

    return {
        "status": "ok",
        "summary": WalletSummary(available_balance=w.available_balance, blocked_balance=w.blocked_balance).model_dump(),
    }

# Alias for spec name
@router.post("/deposit")
def deposit_alias(payload: TopupPayload, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return topup_wallet(payload, session, current_user)


@router.patch("/add-test-balance")
async def add_test_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.partner_balance = (wallet.partner_balance or Decimal("0.00")) + Decimal("500")
    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return {"message": "Balance added", "new_balance": wallet.partner_balance}


class BlockPayload(SQLModel):
    reservation_id: int
    amount: Decimal


@router.post("/block")
def block_amount(
    payload: BlockPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    w = _get_or_create_wallet(session, current_user.id)
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Geçerli bir tutar girin")
    if w.available_balance < payload.amount:
        raise HTTPException(status_code=400, detail="Bakiyeniz yetersiz")
    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    w.available_balance = w.available_balance - payload.amount
    w.blocked_balance = w.blocked_balance + payload.amount
    r.total_amount = payload.amount
    session.add(w)
    session.add(r)
    session.commit()
    session.refresh(w)

    tx = WalletTransaction(user_id=current_user.id, type="reservation_hold", amount=payload.amount, description=f"Rezervasyon blokajı #{r.id}", related_reservation_id=r.id)
    session.add(tx)
    session.commit()

    return WalletSummary(available_balance=w.available_balance, blocked_balance=w.blocked_balance)


class ReleasePayload(SQLModel):
    reservation_id: int


@router.post("/release")
def release_payment(
    payload: ReleasePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    r = session.get(Reservation, payload.reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    w = _get_or_create_wallet(session, (r.partner_id or r.created_by_user_id or current_user.id))
    amount = r.total_amount or Decimal("0.00")
    if w.blocked_balance < amount:
        raise HTTPException(status_code=400, detail="Bloke bakiye yetersiz")
    from ..config import settings
    commission_rate = getattr(settings, "SYSTEM_FEE_PERCENT", 0.10)
    commission = (amount * Decimal(str(commission_rate))).quantize(Decimal("0.01"))
    payout = (amount - commission).quantize(Decimal("0.01"))
    w.blocked_balance = w.blocked_balance - amount
    session.add(w)
    r.status = "completed"
    r.payment_status = "paid"
    session.add(r)
    session.commit()
    # Log transactions
    tx_comm = WalletTransaction(user_id=(r.partner_id or r.created_by_user_id or current_user.id), type="commission", amount=commission, description=f"Komisyon kesinti #{r.id}", related_reservation_id=r.id)
    tx_payout = WalletTransaction(user_id=(r.partner_id or r.created_by_user_id or current_user.id), type="driver_payout", amount=payout, description=f"Sürücü ödemesi #{r.id}", related_reservation_id=r.id)
    session.add(tx_comm)
    session.add(tx_payout)
    session.commit()
    return {"status": "ok", "commission": str(commission), "payout": str(payout)}