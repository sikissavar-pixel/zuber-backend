from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from ..database import get_session
from ..auth import require_role
from ..models.applications import PartnerPending, DriverPending
from ..services.mailer import send_email, MailerError
from ..socket import sio
import asyncio

router = APIRouter(prefix="/api/admin/applications", tags=["admin-documents"])


class MissingDocumentRequest(BaseModel):
    missing_document_note: str
    application_type: str  # "driver" or "partner"


@router.post("/{app_id}/approve-documents", dependencies=[Depends(require_role("admin"))])
def approve_documents(
    app_id: int,
    application_type: str,
    session: Session = Depends(get_session)
):
    if application_type == "driver":
        app = session.get(DriverPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app.document_status = "approved"
    elif application_type == "partner":
        app = session.get(PartnerPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app.document_status = "approved"
    else:
        raise HTTPException(status_code=400, detail="Invalid application type")
    
    session.add(app)
    session.commit()
    
    try:
        sio.start_background_task(
            asyncio.run,
            sio.emit("application_documents_updated", {
                "type": application_type,
                "application_id": app_id,
                "document_status": "approved"
            }, to="admin_room")
        )
    except Exception:
        pass
    
    return {"success": True, "document_status": "approved"}


@router.post("/{app_id}/reject-documents", dependencies=[Depends(require_role("admin"))])
def reject_documents(
    app_id: int,
    application_type: str,
    session: Session = Depends(get_session)
):
    if application_type == "driver":
        app = session.get(DriverPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app.document_status = "rejected"
    elif application_type == "partner":
        app = session.get(PartnerPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        app.document_status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid application type")
    
    session.add(app)
    session.commit()
    
    try:
        sio.start_background_task(
            asyncio.run,
            sio.emit("application_documents_updated", {
                "type": application_type,
                "application_id": app_id,
                "document_status": "rejected"
            }, to="admin_room")
        )
    except Exception:
        pass
    
    return {"success": True, "document_status": "rejected"}


@router.post("/{app_id}/request-missing-documents", dependencies=[Depends(require_role("admin"))])
def request_missing_documents(
    app_id: int,
    payload: MissingDocumentRequest,
    session: Session = Depends(get_session)
):
    if payload.application_type == "driver":
        app = session.get(DriverPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        email = app.email
        full_name = app.full_name
    elif payload.application_type == "partner":
        app = session.get(PartnerPending, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        email = app.contact_email
        full_name = app.contact_full_name
    else:
        raise HTTPException(status_code=400, detail="Invalid application type")
    
    app.document_status = "missing"
    app.missing_document_note = payload.missing_document_note
    session.add(app)
    
    try:
        upload_url = "https://zuber-37e2.vercel.app/driver/apply" if payload.application_type == "driver" else "https://zuber-37e2.vercel.app/partner/apply"
        
        email_html = f"""
        <h3>Zuber İstanbul - Eksik Belge Bildirimi</h3>
        <p>Sayın {full_name},</p>
        <p>Başvurunuzda eksik belge tespit edilmiştir:</p>
        <p><b>{payload.missing_document_note}</b></p>
        <p>Lütfen eksik belgeleri yüklemek için aşağıdaki linke tıklayınız:</p>
        <p><a href='{upload_url}'>Belgeleri Yükle</a></p>
        <br/>
        <b>Zuber İstanbul</b>
        """
        
        send_email("Zuber - Eksik Belge Bildirimi", [email], email_html)
        session.commit()
    except MailerError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(exc)}")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to request missing documents: {str(exc)}")
    
    try:
        sio.start_background_task(
            asyncio.run,
            sio.emit("application_documents_updated", {
                "type": payload.application_type,
                "application_id": app_id,
                "document_status": "missing"
            }, to="admin_room")
        )
    except Exception:
        pass
    
    return {"success": True, "document_status": "missing"}

