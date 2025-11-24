from fastapi import APIRouter, Depends
from sqlmodel import Session, select, SQLModel
from sqlalchemy import text
from ..database import get_session, engine
from ..auth import require_role, get_password_hash
from ..models.user import User
from ..models.partner import Partner
from ..models.applications import PartnerPending, DriverPending
from ..socket import sio
import asyncio

router = APIRouter(prefix="/api/admin/tools", tags=["admin"])


class ResetPayload(SQLModel):
    admin_email: str = "admin@zuber.com"
    admin_full_name: str = "Admin"
    admin_password: str | None = None


@router.post("/reset", dependencies=[Depends(require_role("admin"))])
def reset_database(payload: ResetPayload | None = None, session: Session = Depends(get_session)):
    # Resolve admin fields
    admin_email = (payload.admin_email if payload and payload.admin_email else "admin@zuber.com").strip()
    admin_full_name = (payload.admin_full_name if payload and payload.admin_full_name else "Admin").strip()
    admin_password = (payload.admin_password if payload and payload.admin_password else "admin123")

    # 1) Wipe partners and applications
    for p in session.exec(select(Partner)).all():
        session.delete(p)
    for app in session.exec(select(PartnerPending)).all():
        session.delete(app)
    for app in session.exec(select(DriverPending)).all():
        session.delete(app)
    session.commit()

    # 2) Wipe users except admin_email
    for u in session.exec(select(User).where(User.email != admin_email)).all():
        session.delete(u)
    session.commit()

    # Ensure admin user exists
    admin = session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, full_name=admin_full_name, role="admin", password_hash=get_password_hash(admin_password))
        session.add(admin)
        session.commit()
        session.refresh(admin)

    # 3) Reset ID counters to start from 1 again (SQLite) and set admin id=1 when possible
    try:
        with engine.begin() as conn:
            dialect = conn.dialect.name
            if dialect == "sqlite":
                # Reset sequences for emptied tables
                conn.exec_driver_sql("DELETE FROM sqlite_sequence WHERE name IN ('user','partner','driverpending','partnerpending')")
                # Force admin id to be 1
                conn.exec_driver_sql("UPDATE user SET id = 1 WHERE email = :email", {"email": admin_email})
            else:
                # Best-effort for other dialects: attempt to set admin id then rely on ORM autoincrement
                conn.execute(text("UPDATE \"user\" SET id = 1 WHERE email = :email"), {"email": admin_email})
    except Exception:
        # Non-critical in dev; continue
        pass

    # Refresh admin row after potential id update
    session.commit()
    admin = session.exec(select(User).where(User.email == admin_email)).first()

    # Broadcast to admin room for UI to refresh
    try:
        sio.start_background_task(asyncio.run, sio.emit("admin_reset", {"ok": True, "admin_email": admin_email, "admin_id": admin.id}, to="admin_room"))
    except Exception:
        pass

    return {
        "status": "ok",
        "admin": {"id": admin.id, "email": admin.email, "full_name": admin.full_name},
        "cleared_tables": ["partner", "partnerpending", "driverpending", "user_except_admin"],
    }