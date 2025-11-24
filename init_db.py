#!/usr/bin/env python3
"""
Initialize database with admin user if it doesn't exist.
This runs before uvicorn starts to ensure admin user is always present.
"""
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models.user import User
from app.auth import get_password_hash

def main():
    print("🔧 Initializing database...")
    init_db()
    
    with Session(engine) as session:
        # Check if admin user already exists
        existing_admin = session.exec(
            select(User).where(User.email == "ysr@gmail.com")
        ).first()
        
        if existing_admin:
            print("✅ Admin user already exists: ysr@gmail.com")
        else:
            print("🔑 Creating admin user: ysr@gmail.com")
            admin = User(
                email="ysr@gmail.com",
                password_hash=get_password_hash("Aslan123"),
                full_name="Yasir Admin",
                role="admin"
            )
            session.add(admin)
            session.commit()
            print("✅ Admin user created successfully!")
    
    print("🎉 Database initialization complete!")

if __name__ == "__main__":
    main()
