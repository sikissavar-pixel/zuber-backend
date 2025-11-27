from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "VIP Istanbul Transfer API"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str
    # Allow common dev hosts/ports by default; can be overridden via .env
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,"
        "http://127.0.0.1:3000,http://127.0.0.1:3002"
    )
    SOCKET_CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,"
        "http://127.0.0.1:3000,http://127.0.0.1:3002"
    )
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    GOOGLE_PLAY_PACKAGE_NAME: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str = ""
    SYSTEM_FEE_PERCENT: float = 0.10
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_MAPS_SERVER_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()  # type: ignore