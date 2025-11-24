from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select, SQLModel
from ..database import get_session
from ..models.reservation import Reservation, ReservationCreate, ReservationRead
from ..auth import get_current_user, require_role
from ..models.user import User
from ..socket import sio

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


def _find_available_driver(session: Session) -> Optional[int]:
    """Basic auto-assign: pick the first driver user."""
    driver = session.exec(select(User).where(User.role == "driver")).first()
    return driver.id if driver else None


@router.post("/", response_model=ReservationRead)
def create_reservation(
    payload: ReservationCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"guest", "partner", "admin"}:
        raise HTTPException(status_code=403, detail="Not allowed to create reservations")

    data = payload.model_dump()
    r = Reservation(**data)
    r.created_by_user_id = current_user.id
    if current_user.role == "guest":
        r.guest_id = current_user.id
    elif current_user.role == "partner":
        r.partner_id = r.partner_id or None  # partner linkage could be added later

    # New reservations start as pending & unpaid
    r.status = "pending"
    r.payment_status = "unpaid"

    # Optional: auto-assign a driver
    driver_id = _find_available_driver(session)
    if driver_id:
        r.driver_id = driver_id
        r.status = "assigned"

    session.add(r)
    session.commit()
    session.refresh(r)

    # Broadcast creation
    background_tasks.add_task(sio.emit, "reservation_created", ReservationRead.model_validate(r).model_dump())
    if r.driver_id:
        background_tasks.add_task(sio.emit, "reservation_assigned", ReservationRead.model_validate(r).model_dump())

    return ReservationRead.model_validate(r)


@router.get("/me", response_model=list[ReservationRead])
def my_reservations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "guest":
        rows = session.exec(select(Reservation).where(Reservation.guest_id == current_user.id)).all()
    elif current_user.role == "driver":
        rows = session.exec(select(Reservation).where(Reservation.driver_id == current_user.id)).all()
    elif current_user.role == "partner":
        rows = session.exec(select(Reservation).where(Reservation.created_by_user_id == current_user.id)).all()
    elif current_user.role == "admin":
        rows = session.exec(select(Reservation)).all()
    else:
        rows = []
    return [ReservationRead.model_validate(r) for r in rows]


@router.get("/admin", response_model=list[ReservationRead], dependencies=[Depends(require_role("admin"))])
def admin_list_reservations(session: Session = Depends(get_session)):
    rows = session.exec(select(Reservation)).all()
    return [ReservationRead.model_validate(r) for r in rows]


class StatusUpdate(SQLModel):
    status: str


@router.patch("/{reservation_id}/status", response_model=ReservationRead)
def update_status(
    reservation_id: int,
    payload: StatusUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    r = session.get(Reservation, reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    allowed_status = {"pending", "assigned", "in_progress", "completed", "cancelled"}
    if payload.status not in allowed_status:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Driver can only update their assigned reservations
    if current_user.role == "driver":
        if r.driver_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your reservation")
    elif current_user.role not in {"admin"}:
        raise HTTPException(status_code=403, detail="Not allowed")

    r.status = payload.status
    session.add(r)
    session.commit()
    session.refresh(r)

    background_tasks.add_task(sio.emit, "reservation_updated", ReservationRead.model_validate(r).model_dump())

    return ReservationRead.model_validate(r)


class AssignPayload(SQLModel):
    driver_id: Optional[int] = None


@router.patch("/{reservation_id}/assign_driver", response_model=ReservationRead, dependencies=[Depends(require_role("admin"))])
def assign_driver(
    reservation_id: int,
    payload: AssignPayload,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    r = session.get(Reservation, reservation_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    driver_id = payload.driver_id or _find_available_driver(session)
    if not driver_id:
        raise HTTPException(status_code=400, detail="No available drivers")

    r.driver_id = driver_id
    r.status = "assigned"
    session.add(r)
    session.commit()
    session.refresh(r)

    background_tasks.add_task(sio.emit, "reservation_assigned", ReservationRead.model_validate(r).model_dump())
    background_tasks.add_task(sio.emit, "reservation_updated", ReservationRead.model_validate(r).model_dump())

    return ReservationRead.model_validate(r)