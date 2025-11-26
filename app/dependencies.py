from typing import Generator
from sqlalchemy.orm import Session as AlchemySession
from .database import get_session
from .auth import get_current_user as _get_current_user

def get_db() -> Generator[AlchemySession, None, None]:
    yield from get_session()

get_current_user = _get_current_user

__all__ = ["get_db", "get_current_user"]
