from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, SQLModel, Field
from ..auth import get_current_user
from ..database import get_session
from ..models.user import User
from ..models.driver_location import DriverLocation
from ..services.maps import get_route_estimate

router = APIRouter(prefix="/api/maps", tags=["maps"])


class RouteWaypoint(SQLModel):
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None

    def to_query(self) -> str:
        if self.latitude is not None and self.longitude is not None:
            return f"{self.latitude},{self.longitude}"
        if self.address:
            return self.address
        raise HTTPException(status_code=400, detail="Geçerli bir konum bilgisi gerekli")


class RouteEstimateRequest(SQLModel):
    origin: RouteWaypoint
    destination: RouteWaypoint
    travel_mode: str | None = "driving"


@router.post("/route/estimate")
async def route_estimate(
    payload: RouteEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Yetkilendirme gerekli")
    return await get_route_estimate(
        origin=payload.origin.to_query(),
        destination=payload.destination.to_query(),
        travel_mode=payload.travel_mode or "driving",
    )


@router.get("/driver/{driver_id}/location")
def fetch_driver_location(
    driver_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Yetkilendirme gerekli")
    location = session.exec(select(DriverLocation).where(DriverLocation.driver_id == driver_id)).first()
    if not location:
        raise HTTPException(status_code=404, detail="Konum bulunamadı")
    data = location.model_dump()
    data["driverId"] = data["driver_id"]
    data["lat"] = data["latitude"]
    data["lng"] = data["longitude"]
    return data

