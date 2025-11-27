from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Optional, List
from ..database import get_session
from ..auth import require_role

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/login-attempts", dependencies=[Depends(require_role("admin"))])
def get_login_attempts(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, le=100),
):
    try:
        import os
        log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "admin_login.log")
        attempts = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    parts = line.strip().split(" | ")
                    if len(parts) >= 3:
                        attempts.append({
                            "timestamp": parts[0],
                            "action": parts[1],
                            "details": " | ".join(parts[2:]) if len(parts) > 2 else "",
                        })
        return {"items": attempts[-limit:], "total": len(attempts)}
    except Exception:
        return {"items": [], "total": 0}


@router.get("/sessions", dependencies=[Depends(require_role("admin"))])
def get_sessions(session: Session = Depends(get_session)):
    return {"items": [], "total": 0, "active": 0}


@router.get("/blocked-ips", dependencies=[Depends(require_role("admin"))])
def get_blocked_ips(session: Session = Depends(get_session)):
    return {"items": [], "total": 0}

