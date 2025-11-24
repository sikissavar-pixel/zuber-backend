from sqlmodel import Session
from app.database import engine, init_db
from app.models.user import User
from app.auth import get_password_hash
from app.models.vehicle import Vehicle
from app.models.partner import Partner
from app.models.reservation import Reservation
from datetime import datetime, timedelta
from sqlmodel import select

def run():
    init_db()
    with Session(engine) as session:
        # Admin user (legacy)
        admin = User(email="admin@vip.com", password_hash=get_password_hash("admin123"), full_name="Admin", role="admin")
        session.add(admin)

        # Cleanup any existing users with the special admin email to avoid duplicates
        existing_special = session.exec(select(User).where(User.email == "ysr@gmail.com")).all()
        for u in existing_special:
            session.delete(u)
        session.commit()

        # Admin user (special credentials expected by login: ysr@gmail.com / Aslan1123)
        special_admin = User(email="ysr@gmail.com", password_hash=get_password_hash("Aslan1123"), full_name="Yasir Admin", role="admin")
        session.add(special_admin)

        # Driver user
        driver = User(email="driver@vip.com", password_hash=get_password_hash("driver123"), full_name="Driver One", role="driver")
        session.add(driver)

        # Partner
        hotel = Partner(name="Grand Istanbul Hotel", contact_email="concierge@grandhotel.com", contact_phone="+90 555 000 0000")
        session.add(hotel)

        # Vehicles
        session.add(Vehicle(plate="34 VIP 001", model="Mercedes V-Class", capacity=6))
        session.add(Vehicle(plate="34 VIP 002", model="BMW 7 Series", capacity=4))
        session.commit()
        session.refresh(driver)
        session.refresh(hotel)

        # Demo reservation assigned to driver (ID auto-increment)
        r = Reservation(
            pickup_location="Grand Istanbul Hotel",
            dropoff_location="IST Airport",
            pickup_time=datetime.utcnow() + timedelta(hours=2),
            status="assigned",
            payment_status="unpaid",
            total_amount=350,
            driver_id=driver.id,
            partner_id=hotel.id,
            created_by_user_id=None,
            guest_name="Demo Guest",
        )
        session.add(r)
        session.commit()
        print("Seed completed.")

if __name__ == "__main__":
    run()