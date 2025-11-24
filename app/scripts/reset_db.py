"""
One-time cleanup script: deletes all partners, drivers, and reservations,
keeps only the admin user (email: admin@zuber.com), and resets SQLite IDs.

Run with: python -m app.scripts.reset_db
"""

from sqlmodel import Session, select
from ..database import engine
from ..models.user import User
from ..models.partner import Partner
from ..models.reservation import Reservation


def main():
    with Session(engine) as session:
        # Delete all partners
        partners = session.exec(select(Partner)).all()
        for p in partners:
            session.delete(p)

        # Delete all reservations
        reservations = session.exec(select(Reservation)).all()
        for r in reservations:
            session.delete(r)

        # Delete users except admin
        users = session.exec(select(User)).all()
        for u in users:
            if u.email != "admin@zuber.com":
                session.delete(u)

        session.commit()

        # Reset SQLite autoincrement counters
        try:
            conn = session.connection()
            conn.exec_driver_sql("DELETE FROM sqlite_sequence WHERE name IN ('user','partner','reservation')")
        except Exception:
            pass

    print("✅ All partners, drivers, and reservations wiped. Admin preserved.")


if __name__ == "__main__":
    main()