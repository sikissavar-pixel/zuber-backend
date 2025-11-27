import os
from cryptography.fernet import Fernet
from ..config import settings

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
else:
    if len(ENCRYPTION_KEY.encode()) != 44:
        ENCRYPTION_KEY = Fernet.generate_key().decode()

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_tc(tc_no: str) -> str:
    if not tc_no or len(tc_no) != 11:
        raise ValueError("Invalid TC number length")
    return fernet.encrypt(tc_no.encode()).decode()

def decrypt_tc(encrypted_tc: str) -> str:
    if not encrypted_tc:
        raise ValueError("Empty encrypted TC")
    return fernet.decrypt(encrypted_tc.encode()).decode()

def mask_tc(tc_no: str) -> str:
    if not tc_no or len(tc_no) != 11:
        return "******"
    return "******" + tc_no[-2:]

