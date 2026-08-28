from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import re

from models import SessionLocal, EventLog, SystemSetting, PortalAccount, Lease, BookingTask, Tenant, Applicant

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
    device_id = payload.get("device_id", "") # e.g. recipient SIM phone number from SMS Gateway
    
    # 1. Dynamic OTP extraction from SystemSetting with fallback
    otp_code = None
    if text:
        setting = db.query(SystemSetting).filter(SystemSetting.key == "otp.regex_pattern").first()
        configured_pattern = setting.value if setting and setting.value else None
        
        # Try configured pattern first
        if configured_pattern:
            try:
                match = re.search(configured_pattern, text, re.IGNORECASE)
                if match:
                    otp_code = match.group(1) if match.groups() else match.group(0)
            except Exception:
                pass
                
        # Priority fallback: Gerry's GVCW Appointment format ("The OTP for your GVCW Appointment is: 55613")
        if not otp_code:
            match = re.search(r'The OTP for your GVCW Appointment is:\s*(\d{4,8})', text, re.IGNORECASE)
            if match:
                otp_code = match.group(1)
                
        # Secondary fallback: Generic OTP format
        if not otp_code:
            match = re.search(r'(?:OTP|code).*?[:\s]+(\d{4,8})', text, re.IGNORECASE)
            if match:
                otp_code = match.group(1)
                
        # Tertiary fallback: Standalone 5 or 6 digit number
        if not otp_code:
            match = re.search(r'\b\d{5,6}\b', text)
            if match:
                otp_code = match.group(0)
            
    # 2. Record EventLog
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
    
    # 3. Direct Mapping: Route OTP to the active BookingTask
    if otp_code:
        active_task = None
        
        # Strategy A: Match by leased PortalAccount's phone_number
        if device_id:
            account = db.query(PortalAccount).filter(PortalAccount.phone_number == device_id).first()
            if account:
                active_lease = db.query(Lease).filter(
                    Lease.portal_account_id == account.id,
                    Lease.status.in_(["Leased", "Running", "Pending"])
                ).order_by(Lease.id.desc()).first()
                if active_lease and active_lease.booking_task_id:
                    active_task = db.query(BookingTask).filter(BookingTask.id == active_lease.booking_task_id).first()

        # Strategy B: Match by Tenant phone_number
        if not active_task and device_id:
            tenant = db.query(Tenant).filter(Tenant.phone_number == device_id).first()
            if tenant:
                active_task = db.query(BookingTask).filter(
                    BookingTask.tenant_id == tenant.id,
                    BookingTask.status.in_(["PENDING", "CLAIMED", "PROCESSING"])
                ).order_by(BookingTask.id.desc()).first()

        # Strategy C: Fallback to most recent in-flight BookingTask
        if not active_task:
            active_task = db.query(BookingTask).filter(
                BookingTask.status.in_(["CLAIMED", "PROCESSING", "PENDING"])
            ).order_by(BookingTask.id.desc()).first()
            
        if active_task:
            active_task.otp_code = otp_code
                
    db.commit()
    
    return {"status": "ok", "extracted_otp": otp_code}

@router.post("/manual-otp")
async def submit_manual_otp(request: Request, db: Session = Depends(get_db)):
    """Allows staff/operators to manually inject an OTP for a specific or latest active booking task."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
        
    otp_code = str(payload.get("otp_code", "")).strip()
    task_id = payload.get("task_id")
    
    if not otp_code:
        return {"status": "error", "message": "OTP code is required"}
        
    task = None
    if task_id:
        task = db.query(BookingTask).filter(BookingTask.id == int(task_id)).first()
    else:
        # Pick the most active in-flight task
        task = db.query(BookingTask).filter(
            BookingTask.status.in_(["CLAIMED", "PROCESSING", "PENDING"])
        ).order_by(BookingTask.id.desc()).first()
        
    if not task:
        return {"status": "error", "message": "No active booking task found to assign OTP"}
        
    task.otp_code = otp_code
    
    log = EventLog(
        source="staff_manual_otp",
        severity="info",
        event_type="MANUAL_OTP_ENTERED",
        assignment_id=task.id,
        payload={
            "task_id": task.id,
            "otp_code": otp_code,
            "target_date": task.target_date,
            "target_time": task.target_time
        }
    )
    db.add(log)
    db.commit()
    
    return {
        "status": "ok",
        "message": f"OTP {otp_code} manually assigned to Task #{task.id}",
        "task_id": task.id
    }

