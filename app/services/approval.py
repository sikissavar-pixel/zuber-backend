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


EMAIL_HTML_TEMPLATE = """
<h3>Zuber İstanbul'a Hoş Geldiniz</h3>
<p>Başvurunuz başarıyla onaylandı.</p>
<p><b>E-posta:</b> {email}</p>
<p><b>Geçici Şifre:</b> {password}</p>
<p>Giriş: <a href='https://zuber-37e2.vercel.app/login'>https://zuber-37e2.vercel.app/login</a></p>
<p>Lütfen ilk girişte şifrenizi değiştiriniz.</p>
<br/>
<b>Zuber İstanbul</b>
"""


def send_approval_email(full_name: str, email: str, password: str):
    html_body = EMAIL_HTML_TEMPLATE.format(email=email, password=password)
    send_email("Zuber Hesabınız Onaylandı", [email], html_body)
