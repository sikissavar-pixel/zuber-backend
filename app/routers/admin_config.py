from fastapi import APIRouter, Depends, HTTPException
from ..auth import require_role
from ..config import settings
from sqlmodel import SQLModel

router = APIRouter(prefix="/api/admin/config", tags=["admin"])


class SetFeePayload(SQLModel):
    system_fee_percent: float


@router.post("/system_fee_percent", dependencies=[Depends(require_role("admin"))])
def set_system_fee(payload: SetFeePayload):
    if payload.system_fee_percent < 0 or payload.system_fee_percent > 1:
        raise HTTPException(status_code=400, detail="Komisyon 0-1 aralığında olmalı")
    settings.SYSTEM_FEE_PERCENT = payload.system_fee_percent
    return {"status": "ok", "system_fee_percent": settings.SYSTEM_FEE_PERCENT}