import os
import httpx
from typing import Iterable

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_API_URL = "https://api.resend.com/emails"


class MailerError(Exception):
    pass


def send_email(subject: str, recipients: Iterable[str], body: str):
    if not RESEND_API_KEY:
        raise MailerError("RESEND_API_KEY not configured")
    
    recipient_list = list(recipients)
    if not recipient_list:
        raise MailerError("No recipients provided")
    
    payload = {
        "from": "Zuber İstanbul <zuberistanbul@gmail.com>",
        "to": recipient_list,
        "subject": subject,
        "html": body,
    }
    
    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10.0,
        )
        
        if response.status_code != 200:
            error_detail = response.text or f"HTTP {response.status_code}"
            raise MailerError(f"Resend API error: {error_detail}")
        
        return response.json()
    except httpx.RequestError as exc:
        raise MailerError(f"Network error: {str(exc)}") from exc
    except Exception as exc:
        raise MailerError(str(exc)) from exc
