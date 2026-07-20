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
    db.commit()
    
    return {"status": "ok", "extracted_otp": otp_code}
