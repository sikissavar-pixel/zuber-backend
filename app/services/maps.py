import httpx
from fastapi import HTTPException
from ..config import settings

GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


async def get_route_estimate(origin: str, destination: str, travel_mode: str = "driving"):
    api_key = settings.GOOGLE_MAPS_SERVER_KEY or settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Google Maps API anahtarı tanımlı değil")

    params = {
        "origin": origin,
        "destination": destination,
        "mode": travel_mode,
        "language": "tr",
        "region": "tr",
        "key": api_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(GOOGLE_DIRECTIONS_URL, params=params)
    data = response.json()
    status = data.get("status")
    if status != "OK":
        message = data.get("error_message") or status or "Rota oluşturulamadı"
        raise HTTPException(status_code=400, detail=message)

    route = data["routes"][0]
    leg = route["legs"][0]
    distance_meters = leg["distance"]["value"]
    duration_seconds = leg["duration"]["value"]
    polyline = route.get("overview_polyline", {}).get("points")

    distance_km = distance_meters / 1000
    duration_minutes = duration_seconds / 60

    base_fare = 350.0
    per_km = 42.5
    per_minute = 6.0

    partner_price = base_fare + (distance_km * per_km) + (duration_minutes * per_minute)
    driver_share = partner_price * (1 - (settings.SYSTEM_FEE_PERCENT or 0.10))

    return {
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "polyline": polyline,
        "origin": {
            "lat": leg["start_location"]["lat"],
            "lng": leg["start_location"]["lng"],
            "address": leg["start_address"],
        },
        "destination": {
            "lat": leg["end_location"]["lat"],
            "lng": leg["end_location"]["lng"],
            "address": leg["end_address"],
        },
        "fare": {
            "currency": "TRY",
            "partner_price": round(partner_price, 2),
            "driver_payout": round(driver_share, 2),
            "base_fare": base_fare,
            "per_km": per_km,
            "per_minute": per_minute,
            "system_fee_percent": settings.SYSTEM_FEE_PERCENT,
        },
    }

