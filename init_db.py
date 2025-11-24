#!/usr/bin/env python3
"""
Initialize database with admin user if it doesn't exist.
This runs before uvicorn starts to ensure admin user is always present.
"""
from sqlmodel import Session, select

from app.database import engine
from app.models.user import User
from app.auth import get_password_hash


def init_admin() -> None:
    email = "ysr@gmail.com"
    password = "Aslan123"
    hashed = get_password_hash(password)

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user:
            print("✔ Admin already exists:", email)
            return

        admin = User(
            email=email,
            password_hash=hashed,
            role="admin",
            full_name="Yasir Admin",
        )
        session.add(admin)
        session.commit()
        print("✔ Admin created:", email)


if __name__ == "__main__":
    init_admin()
