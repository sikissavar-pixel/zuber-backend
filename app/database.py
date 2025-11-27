from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from .config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)

def init_db():
    from .models.base import BaseModel
    from .models.user import User
    from .models.vehicle import Vehicle
    from .models.partner import Partner
    from .models.reservation import Reservation
    from .models.payment import Payment
    from .models.booking_message import BookingMessage
    from .models.wallet import Wallet, WalletTransaction
    from .models.feedback import Feedback
    from .models.driver_location import DriverLocation
    from .models.applications import PartnerPending, DriverPending
    SQLModel.metadata.create_all(engine)

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
                add_user_col("must_change_password", "INTEGER")
                pcols = conn.exec_driver_sql("PRAGMA table_info('partner')").fetchall()
                pnames = {c[1] for c in pcols}
                if "approved" not in pnames:
                    try:
                        conn.exec_driver_sql("ALTER TABLE partner ADD COLUMN approved INTEGER DEFAULT 0")
                    except Exception:
                        pass
                if "created_at" not in pnames:
                    try:
                        conn.exec_driver_sql("ALTER TABLE partner ADD COLUMN created_at TEXT")
                    except Exception:
                        pass
                dpcols = conn.exec_driver_sql("PRAGMA table_info('driverpending')").fetchall()
                dpnames = {c[1] for c in dpcols} if dpcols else set()
                def add_dp_col(name: str, type_sql: str = "TEXT"):
                    if name not in dpnames:
                        try:
                            conn.exec_driver_sql(f"ALTER TABLE driverpending ADD COLUMN {name} {type_sql}")
                        except Exception:
                            pass
                for col, col_type in [
                    ("tc_no_encrypted", "TEXT"),
                    ("birth_year", "INTEGER"),
                    ("driver_license_class", "TEXT"),
                    ("driver_license_year", "INTEGER"),
                    ("criminal_record_confirmed", "INTEGER"),
                    ("kvkk_consent", "INTEGER"),
                    ("data_processing_consent", "INTEGER"),
                    ("vehicle_brand", "TEXT"),
                    ("vehicle_model", "TEXT"),
                    ("vehicle_year", "INTEGER"),
                    ("fuel_type", "TEXT"),
                    ("driver_license_image_url", "TEXT"),
                    ("vehicle_registration_image_url", "TEXT"),
                    ("document_status", "TEXT"),
                    ("missing_document_note", "TEXT"),
                    ("reject_reason", "TEXT"),
                    ("rejected_at", "TEXT"),
                ]:
                    add_dp_col(col, col_type)
                ppcols = conn.exec_driver_sql("PRAGMA table_info('partnerpending')").fetchall()
                ppnames = {c[1] for c in ppcols} if ppcols else set()
                def add_pp_col(name: str, type_sql: str = "TEXT"):
                    if name not in ppnames:
                        try:
                            conn.exec_driver_sql(f"ALTER TABLE partnerpending ADD COLUMN {name} {type_sql}")
                        except Exception:
                            pass
                for col, col_type in [
                    ("company_name", "TEXT"),
                    ("tax_office", "TEXT"),
                    ("tax_number", "TEXT"),
                    ("company_type", "TEXT"),
                    ("tc_no_encrypted", "TEXT"),
                    ("total_vehicles", "INTEGER"),
                    ("fleet_type", "TEXT"),
                    ("kvkk_consent", "INTEGER"),
                    ("commercial_contract_approved", "INTEGER"),
                    ("company_documents_image_url", "TEXT"),
                    ("document_status", "TEXT"),
                    ("missing_document_note", "TEXT"),
                    ("reject_reason", "TEXT"),
                    ("rejected_at", "TEXT"),
                ]:
                    add_pp_col(col, col_type)
    except Exception:
        pass

def get_session():
    with Session(engine) as session:
        yield session
