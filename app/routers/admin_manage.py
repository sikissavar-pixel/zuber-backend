from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..database import get_session
from ..auth import require_role
from ..models.reservation import Reservation
from ..models.partner import Partner
from ..models.user import User
from ..socket import sio

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.delete("/reservations/{reservation_id}")
def delete_reservation(reservation_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("admin"))):
    reservation = session.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    session.delete(reservation)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("admin_update", {"type": "delete", "table": "reservations", "id": reservation_id}, to="admin_room"))
    except Exception:
        pass
    return {"message": "Deleted successfully"}


@router.delete("/partners/{partner_id}")
def delete_partner_admin(partner_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("admin"))):
    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    session.delete(partner)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("partners_updated", {"partner_id": partner_id, "deleted": True}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("admin_update", {"type": "delete", "table": "partners", "id": partner_id}, to="admin_room"))
    except Exception:
        pass
    return {"message": "Deleted successfully"}


@router.delete("/drivers/{driver_id}")
def delete_driver_admin(driver_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("admin"))):
    user = session.get(User, driver_id)
    if not user:
        raise HTTPException(status_code=404, detail="Driver not found")
    # Protect admin account from deletion
    if user.role == "admin" or user.email == "admin@zuber.com":
        raise HTTPException(status_code=403, detail="Admin account cannot be deleted")
    # Only allow deleting actual drivers
    if user.role != "driver":
        raise HTTPException(status_code=400, detail="Not a driver account")

    # Cleanup reservations assigned to this driver
    reservations = session.exec(select(Reservation).where(Reservation.driver_id == driver_id)).all()
    for r in reservations:
        r.driver_id = None
        session.add(r)
    session.delete(user)
    session.commit()
    try:
        sio.start_background_task(asyncio.run, sio.emit("drivers_updated", {"user_id": driver_id, "deleted": True}, to="admin_room"))
        sio.start_background_task(asyncio.run, sio.emit("admin_update", {"type": "delete", "table": "drivers", "id": driver_id}, to="admin_room"))
        if reservations:
            sio.start_background_task(asyncio.run, sio.emit("reservation_updated", {"reason": "driver_deleted", "driver_id": driver_id}, to="admin_room"))
    except Exception:
        pass
    return {"message": "Deleted successfully"}