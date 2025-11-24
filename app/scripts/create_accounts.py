from decimal import Decimal
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models.user import User
from app.models.partner import Partner
from app.models.wallet import Wallet, WalletTransaction
from app.auth import get_password_hash


def ensure_user(session: Session, full_name: str, email: str, password: str, role: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        return user
    user = User(full_name=full_name, email=email, password_hash=get_password_hash(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_partner(session: Session, name: str, contact_email: str, contact_phone: str | None = None, approved: bool = True) -> Partner:
    partner = session.exec(select(Partner).where(Partner.contact_email == contact_email)).first()
    if partner:
        # ensure approved flag is set
        partner.approved = approved or partner.approved
        if contact_phone is not None:
            partner.contact_phone = contact_phone
        session.add(partner)
        session.commit()
        session.refresh(partner)
        return partner
    partner = Partner(name=name, contact_email=contact_email, contact_phone=contact_phone, approved=approved, active=True)
    session.add(partner)
    session.commit()
    session.refresh(partner)
    return partner


def set_wallet_balance(session: Session, user_id: int, amount: Decimal, description: str = "Admin topup") -> Wallet:
    wallet = session.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
    if not wallet:
        wallet = Wallet(user_id=user_id)
    wallet.available_balance = amount
    session.add(wallet)
    session.commit()
    session.refresh(wallet)
    # record transaction
    tx = WalletTransaction(user_id=user_id, type="topup", amount=amount, description=description)
    session.add(tx)
    session.commit()
    return wallet


def run():
    init_db()
    with Session(engine) as session:
        # 1) Partner account: zuhtu@gmail.com / Zuber123, set balance 1000₺
        partner_user = ensure_user(session, full_name="Zühtü Partner", email="zuhtu@gmail.com", password="Zuber123", role="partner")
        ensure_partner(session, name="Zühtü Partner", contact_email=partner_user.email, contact_phone=None, approved=True)
        set_wallet_balance(session, user_id=partner_user.id, amount=Decimal("1000"), description="Initial balance assignment")

        # 2) Driver account: yesr@gmail.com / Aslan123
        driver_user = ensure_user(session, full_name="Yesr Sürücü", email="yesr@gmail.com", password="Aslan123", role="driver")

        print(f"Created/ensured partner user id={partner_user.id} email={partner_user.email}")
        print(f"Created/ensured driver user id={driver_user.id} email={driver_user.email}")


if __name__ == "__main__":
    run()