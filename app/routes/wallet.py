from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..dependencies import get_db, get_current_user
from ..models import Wallet, User

router = APIRouter()

@router.patch("/add-test-balance")
async def add_test_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.partner_balance += 500
    db.commit()
    db.refresh(wallet)

    return {"message": "Balance added", "new_balance": wallet.partner_balance}
