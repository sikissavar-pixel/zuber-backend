from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..database import get_session
from ..models.vehicle import Vehicle, VehicleCreate
from ..auth import require_role

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

@router.get("/")
def list_vehicles(session: Session = Depends(get_session)):
    return session.exec(select(Vehicle)).all()

@router.post("/", dependencies=[Depends(require_role("admin"))])
def create_vehicle(payload: VehicleCreate, session: Session = Depends(get_session)):
    v = Vehicle(**payload.model_dump())
    session.add(v)
    session.commit()
    session.refresh(v)
    return v