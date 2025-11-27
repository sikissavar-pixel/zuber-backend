from fastapi import APIRouter, Depends
from sqlmodel import Session
from sqlalchemy import text
from ..database import get_session, engine
from ..socket import sio

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def system_status():
    db_status = "ok"
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
    except Exception:
        db_status = "error"

    socket_status = "ok"
    try:
        if not sio or not hasattr(sio, "server"):
            socket_status = "error"
    except Exception:
        socket_status = "error"

    return {
        "api": "ok",
        "db": db_status,
        "socket": socket_status,
    }

