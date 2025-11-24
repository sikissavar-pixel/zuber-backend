import socketio
from .config import settings

# Create a shared Socket.IO server instance for import by routers and main
# Ensure cors_allowed_origins is a list, not a single comma-separated string.
# In dev, allow all origins to simplify local testing
_origins = [o.strip() for o in (settings.SOCKET_CORS_ORIGINS or "").split(",") if o.strip()] or "*"
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_origins)