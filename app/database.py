from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from .config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)

def init_db():
    from .models.base import BaseModel  # ensure models imported
    from .models.user import User
    from .models.vehicle import Vehicle
    from .models.partner import Partner
    from .models.reservation import Reservation
    from .models.payment import Payment
    from .models.booking_message import BookingMessage
    from .models.wallet import Wallet, WalletTransaction
    from .models.feedback import Feedback
    SQLModel.metadata.create_all(engine)

    # Lightweight migration for SQLite: ensure new payment columns exist on reservation table
    try:
        with engine.begin() as conn:
            dialect = conn.dialect.name
            if dialect == "sqlite":
                cols = conn.exec_driver_sql("PRAGMA table_info('reservation')").fetchall()
                names = {c[1] for c in cols}
                if "total_amount" not in names:
                    conn.exec_driver_sql("ALTER TABLE reservation ADD COLUMN total_amount NUMERIC DEFAULT 0")
                if "payment_reference" not in names:
                    conn.exec_driver_sql("ALTER TABLE reservation ADD COLUMN payment_reference TEXT")
                # Ensure new user profile columns exist
                ucols = conn.exec_driver_sql("PRAGMA table_info('user')").fetchall()
                unames = {c[1] for c in ucols}
                def add_user_col(name: str, type_sql: str = "TEXT"):
                    if name not in unames:
                        try:
                            conn.exec_driver_sql(f"ALTER TABLE user ADD COLUMN {name} {type_sql}")
                        except Exception:
                            pass
                for col in [
                    "identity_number",
                    "contact_phone",
                    "vehicle_plate",
                    "vehicle_model",
                    "profile_image_url",
                    "driver_license_url",
                    "vehicle_image_url",
                ]:
                    add_user_col(col, "TEXT")
                # Add security flag for forced password change (SQLite uses INTEGER for booleans)
                add_user_col("must_change_password", "INTEGER")
                # Ensure partner approval column exists
                pcols = conn.exec_driver_sql("PRAGMA table_info('partner')").fetchall()
                pnames = {c[1] for c in pcols}
                if "approved" not in pnames:
                    try:
                        conn.exec_driver_sql("ALTER TABLE partner ADD COLUMN approved INTEGER DEFAULT 0")
                    except Exception:
                        pass
                # Ensure partner created_at column exists (SQLite stores datetime as TEXT)
                if "created_at" not in pnames:
                    try:
                        # SQLite ALTER TABLE ADD COLUMN without default for broad compatibility
                        conn.exec_driver_sql("ALTER TABLE partner ADD COLUMN created_at TEXT")
                    except Exception:
                        pass
    except Exception:
        # Ignore migration errors in dev
        pass

def get_session():
    with Session(engine) as session:
        yield session