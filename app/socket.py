import socketio
from .config import settings

DEFAULT_SOCKET_ORIGINS = [
    "https://zuber-37e2.vercel.app",
    "http://localhost:3000",
]

configured = [o.strip() for o in (settings.SOCKET_CORS_ORIGINS or "").split(",") if o.strip()]
cors_origins = configured or DEFAULT_SOCKET_ORIGINS

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)