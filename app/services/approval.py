import secrets
import string
from typing import Tuple
from sqlmodel import Session, select

from ..auth import get_password_hash
from ..models.user import User
from ..services.mailer import send_email, MailerError


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*()-_=+" for c in password)
        ):
            return password


def ensure_user(session: Session, email: str, name: str, role: str) -> Tuple[User, str]:
    user = session.exec(select(User).where(User.email == email)).first()
    password = generate_password()
    hashed = get_password_hash(password)

    if user:
        user.password_hash = hashed
        user.role = role
        if hasattr(user, "must_change_password"):
            user.must_change_password = True
        session.add(user)
    else:
        user = User(
            full_name=name,
            email=email,
            role=role,
            password_hash=hashed,
            must_change_password=True,
        )
        session.add(user)

    return user, password


def activate_user_flags(user: User):
    for attr in ("is_active", "is_approved"):
        if hasattr(user, attr):
            setattr(user, attr, True)
    if hasattr(user, "must_change_password"):
        setattr(user, "must_change_password", True)


EMAIL_SUBJECT = "Zuber’e Hoş Geldiniz – Başvurunuz Onaylandı 🎉"
EMAIL_BODY = """Merhaba {full_name},

Zuber ailesine hoş geldiniz! 🎉
Driver / Partner başvurunuz başarıyla onaylanmıştır ve hesabınız artık aktiftir.

Giriş bilgileriniz aşağıda yer almaktadır:

E-posta: {email}
Geçici Şifre: {password}

Hesabınıza giriş yapmak için:
https://zuber-37e2.vercel.app/login

Güvenliğiniz için ilk girişten sonra şifrenizi değiştirmenizi önemle rica ederiz.

Artık Zuber üzerinden aktif olarak işlemlerinizi yönetebilir, kazançlarınızı takip edebilir ve sistemi tam kapasite kullanabilirsiniz.

Herhangi bir sorunuz olursa bizimle iletişime geçmekten çekinmeyin.

Keyifli kullanımlar dileriz 🚗✨
Zuber İstanbul
"""


def send_approval_email(full_name: str, email: str, password: str):
    body = EMAIL_BODY.format(full_name=full_name, email=email, password=password)
    send_email(EMAIL_SUBJECT, [email], body)

