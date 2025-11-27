import smtplib
from email.message import EmailMessage
from typing import Iterable
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "")


class MailerError(Exception):
    pass


def send_email(subject: str, recipients: Iterable[str], body: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise MailerError("SMTP configuration missing")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = FROM_EMAIL or SMTP_USER
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(message)
    except Exception as exc:
        raise MailerError(str(exc)) from exc
