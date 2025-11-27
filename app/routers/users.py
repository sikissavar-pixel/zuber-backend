from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from ..database import get_session
from ..models.user import User, UserCreate, UserRead, UserLogin, UserUpdate
from ..models.partner import Partner
from ..models.applications import PartnerPending
from ..auth import get_password_hash, verify_password, create_access_token, get_current_user
import os
from datetime import datetime
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/register", response_model=UserRead)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        hashed = get_password_hash(payload.password)
    except ValueError as e:
        # Return a clear client error instead of a 500 when hashing fails
        raise HTTPException(status_code=400, detail=str(e))
    user = User(full_name=payload.full_name, email=payload.email, password_hash=hashed, role=payload.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)

@router.post("/login")
def login(payload: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        # Prefer invalid credentials if there is already an approved partner record
        partner = session.exec(select(Partner).where(Partner.contact_email == payload.email)).first()
        if partner and getattr(partner, "approved", False):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Otherwise, if there is a pending application, show the pending message
        pending = session.exec(select(PartnerPending).where(PartnerPending.contact_email == payload.email, PartnerPending.status == "pending")).first()
        if pending:
            raise HTTPException(status_code=403, detail="Başvurunuz onaylanmadı")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Admin özel giriş kontrolü: sadece belirlenen email/şifre ile admin erişimi
    if user.role == "admin":
        if not (payload.email == "ysr@gmail.com" and payload.password == "Aslan123"):
            raise HTTPException(status_code=403, detail="Yönetim paneline sadece özel admin hesabı ile giriş yapılabilir")
        # Admin login logla
        try:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(base_dir, exist_ok=True)
            log_path = os.path.join(base_dir, "admin_login.log")
            with open(log_path, "a", encoding="utf-8") as f:
                ts = datetime.utcnow().isoformat()
                f.write(f"{ts} | admin_login | user_id={user.id} | email={user.email}\n")
        except Exception:
            # log hatalarını sessizce geç
            pass
    token = create_access_token(user_id=user.id, role=user.role)
    # Partner approval gate: ensure approved partner exists before allowing login
    if user.role == "partner":
        # Refresh user to ensure we read latest must_change_password, etc.
        session.refresh(user)
        partners = session.exec(select(Partner).where(Partner.contact_email == user.email)).all()
        approved_exists = any(getattr(p, "approved", False) for p in partners)
        if not approved_exists:
            raise HTTPException(status_code=403, detail="Başvurunuz onaylanmadı")
    # include must_change_password to allow client redirect to change-password
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name,
        "id": user.id,
        "must_change_password": getattr(user, "must_change_password", False),
    }

@router.get("/", response_model=list[UserRead])
@router.get("", response_model=list[UserRead], include_in_schema=False)
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()

@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)

@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    updated = False
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
        updated = True
    if payload.email is not None:
        # Ensure email is unique
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = payload.email
        updated = True
    # Extended fields
    if payload.identity_number is not None:
        current_user.identity_number = payload.identity_number
        updated = True
    if payload.contact_phone is not None:
        current_user.contact_phone = payload.contact_phone
        updated = True
    if payload.vehicle_plate is not None:
        current_user.vehicle_plate = payload.vehicle_plate
        updated = True
    if payload.vehicle_model is not None:
        current_user.vehicle_model = payload.vehicle_model
        updated = True
    if payload.profile_image_url is not None:
        current_user.profile_image_url = payload.profile_image_url
        updated = True
    if payload.driver_license_url is not None:
        current_user.driver_license_url = payload.driver_license_url
        updated = True
    if payload.vehicle_image_url is not None:
        current_user.vehicle_image_url = payload.vehicle_image_url
        updated = True
    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
    return UserRead.model_validate(current_user)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
def change_password(
    payload: ChangePassword,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mevcut şifre yanlış")
    # Hash and update
    try:
        new_hash = get_password_hash(payload.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    current_user.password_hash = new_hash
    # Clear the force-change flag
    try:
        # Attribute may not exist on old DB; guard assignment
        setattr(current_user, "must_change_password", False)
    except Exception:
        pass
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return {"status": "ok"}


@router.post("/me/upload")
def upload_me_files(
    profile_image: UploadFile | None = File(default=None),
    driver_license: UploadFile | None = File(default=None),
    vehicle_image: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    base_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "users", str(current_user.id))
    base_dir = os.path.abspath(base_dir)
    os.makedirs(base_dir, exist_ok=True)

    def _save(upload: UploadFile | None, prefix: str) -> str | None:
        if not upload:
            return None
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_name = f"{prefix}_{ts}_{upload.filename.replace(' ', '_')}"
        dest = os.path.join(base_dir, safe_name)
        with open(dest, "wb") as f:
            f.write(upload.file.read())
        # Build public URL
        url = f"/static/uploads/users/{current_user.id}/{safe_name}"
        return url

    profile_url = _save(profile_image, "profile")
    license_url = _save(driver_license, "license")
    vehicle_url = _save(vehicle_image, "vehicle")

    updated = False
    if profile_url:
        current_user.profile_image_url = profile_url
        updated = True
    if license_url:
        current_user.driver_license_url = license_url
        updated = True
    if vehicle_url:
        current_user.vehicle_image_url = vehicle_url
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return JSONResponse({
        "profile_image_url": profile_url or current_user.profile_image_url,
        "driver_license_url": license_url or current_user.driver_license_url,
        "vehicle_image_url": vehicle_url or current_user.vehicle_image_url,
    })