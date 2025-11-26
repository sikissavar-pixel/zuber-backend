import os
import socketio as _socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db, engine
from sqlmodel import Session
from .models.booking_message import BookingMessage
from .models.reservation import Reservation, ReservationRead
from app.routes import wallet
from .routers import users, reservations, payments, vehicles, partners, applications, partner_approval, bookings, wallet as legacy_wallet, admin_config, driver_portal, admin_tools, admin_panel, admin_manage
from .socket import sio

# FastAPI app
app = FastAPI(title=settings.APP_NAME)

# Explicit dev origins to prevent CORS errors across common ports/hosts
default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3002",
    "capacitor://localhost",
]

# Merge with configured origins from .env/config (comma separated)
configured = [o.strip() for o in (settings.CORS_ORIGINS or "").split(",") if o.strip()]
origins = list({*default_origins, *configured})
# Note: Do NOT add CORS middleware to `app` here, as we already wrap the
# top-level ASGI app (`sio_app`) with CORSMiddleware below. Adding it twice
# causes duplicate headers like "Access-Control-Allow-Credentials: true, true"
# which breaks credentialed requests from the browser.

# Initialize DB tables
init_db()

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Routers
app.include_router(users.router)
app.include_router(reservations.router)
app.include_router(bookings.router)
app.include_router(wallet.router, prefix="/api/wallet", tags=["Wallet"])
app.include_router(legacy_wallet.router, prefix="/api/wallet", tags=["wallet"])
app.include_router(payments.router)
app.include_router(vehicles.router)
app.include_router(partners.router)
app.include_router(applications.router)
app.include_router(partner_approval.router)
app.include_router(admin_config.router)
app.include_router(driver_portal.router)
app.include_router(admin_tools.router)
app.include_router(admin_panel.router)
app.include_router(admin_manage.router)

# Serve static files (uploads) - only if directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Socket.IO ASGI app uses the shared server from app/socket.py
# Wrap the top-level ASGI app with CORS so that all responses
# (including redirects and non-API routes) carry CORS headers.
sio_app = CORSMiddleware(
    _socketio.ASGIApp(sio, other_asgi_app=app),
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@sio.event
async def connect(sid, environ):
    print("socket connected", sid)

@sio.event
async def disconnect(sid):
    print("socket disconnected", sid)

@sio.event
async def driver_location_update(sid, data):
    # Broadcast to all watchers (e.g., admin map) with the same event name
    await sio.emit("driver_location_update", data)

# The ASGI app to run with uvicorn is `sio_app`

# --- Chat & Booking update events ---
@sio.event
async def chat_join(sid, data):
    """
    data: { booking_id: int }
    Adds the socket to a room specific to the booking.
    """
    booking_id = data.get("booking_id")
    if not booking_id:
        return
    room = f"booking_{booking_id}"
    await sio.enter_room(sid, room)

@sio.event
async def chat_message(sid, data):
    """
    data: { booking_id: int, sender_role: str, message: str }
    Persists the message and broadcasts to the booking room.
    """
    booking_id = data.get("booking_id")
    sender_role = data.get("sender_role")
    message = data.get("message")
    if not booking_id or not message:
        return
    # Persist
    try:
        with Session(engine) as session:
            bm = BookingMessage(booking_id=booking_id, sender_role=sender_role or "partner", message=message)
            session.add(bm)
            session.commit()
    except Exception:
        # Swallow DB errors in dev to keep chat flowing
        pass
    # Broadcast
    room = f"booking_{booking_id}"
    await sio.emit("chat_message", {"booking_id": booking_id, "sender_role": sender_role, "message": message}, room=room)

@sio.event
async def booking_update(sid, data):
    """Generic booking update broadcaster for notifications."""
    booking_id = (data or {}).get("booking_id")
    room = f"booking_{booking_id}" if booking_id else None
    await sio.emit("booking_update", data, room=room) if room else await sio.emit("booking_update", data)

# --- Driver chat (simple echo) ---
@sio.event
async def driver_chat_message(sid, data):
    """
    data: { text: str, from: "driver" | "partner" }
    Simple echo/broadcast used by the Driver Portal chat page.
    """
    try:
        text = (data or {}).get("text")
        sender = (data or {}).get("from") or "driver"
        if not text:
            return
        await sio.emit("driver_chat_message", {"text": text, "from": sender})
    except Exception:
        # ignore errors in dev
        pass

# --- Admin room join for live applications ---
@sio.event
async def admin_join(sid, data=None):
    """Allow admin socket to join the dedicated admin room for live updates."""
    try:
        await sio.enter_room(sid, "admin_room")
    except Exception:
        pass

# --- Reservation realtime actions ---
@sio.event
async def accept_reservation(sid, data):
    """
    data: { reservation_id: int, driver_id: int }
    Sets driver_id and marks status as 'assigned'. Emits reservation_assigned and reservation_updated.
    """
    try:
        res_id = (data or {}).get("reservation_id")
        driver_id = (data or {}).get("driver_id")
        if not res_id or not driver_id:
            return
        with Session(engine) as session:
            r = session.get(Reservation, int(res_id))
            if not r:
                return
            # Only allow assigning when pending (or unassigned)
            if r.status in {"pending", "assigned"} and (not r.driver_id):
                r.driver_id = int(driver_id)
                r.status = "assigned"
                session.add(r)
                session.commit()
                session.refresh(r)
                payload = ReservationRead.model_validate(r).model_dump()
                await sio.emit("reservation_assigned", payload)
                await sio.emit("reservation_updated", payload)
    except Exception:
        # Avoid crashing on dev errors
        pass

@sio.event
async def trip_started(sid, data):
    """Mark reservation status as in_progress and broadcast update."""
    await _update_status_and_broadcast(data, "in_progress")

@sio.event
async def trip_arrived(sid, data):
    """Mark reservation status as arrived and broadcast update."""
    await _update_status_and_broadcast(data, "arrived")

@sio.event
async def trip_qr_pending(sid, data):
    """Mark reservation status as qr_pending and broadcast update."""
    await _update_status_and_broadcast(data, "qr_pending")

async def _update_status_and_broadcast(data, new_status: str):
    try:
        res_id = (data or {}).get("reservation_id")
        if not res_id:
            return
        with Session(engine) as session:
            r = session.get(Reservation, int(res_id))
            if not r:
                return
            r.status = new_status
            session.add(r)
            session.commit()
            session.refresh(r)
            payload = ReservationRead.model_validate(r).model_dump()
            await sio.emit("reservation_updated", payload)
    except Exception:
        pass