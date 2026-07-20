from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import re

from models import SessionLocal, EventLog

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])

@router.post("/otp")
async def receive_otp(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
        
    text = payload.get("text", "")
    sender = payload.get("sender", "")
    device_id = payload.get("device_id", "")
    
    # Extract 6 digit OTP (GVC standard)
    otp_code = None
    if text:
        match = re.search(r'\b\d{6}\b', text)
        if match:
            otp_code = match.group(0)
            
    # Just log it for now until pending research on OTP mapping is complete
    log = EventLog(
        source="webhook_otp",
        severity="info",
        event_type="OTP_RECEIVED",
        payload={
            "sender": sender,
            "device_id": device_id,
            "text": text,
            "extracted_otp": otp_code
        }
    )
    db.add(log)
    
    # Map to tenant via phone_number (device_id matches phone_number in SMS Gateway)
    from models import Tenant, BookingTask
    if otp_code:
        tenant = db.query(Tenant).filter(Tenant.phone_number == device_id).first()
        if tenant:
            active_task = db.query(BookingTask).filter(
                BookingTask.tenant_id == tenant.id,
                BookingTask.status == 'PROCESSING'
            ).order_by(BookingTask.updated_at.desc()).first()
            
            if active_task:
                active_task.otp_code = otp_code
                
    db.commit()
    
    return {"status": "ok", "extracted_otp": otp_code}
