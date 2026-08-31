from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import os

from models import get_db, OTPChallenge, BookingTask, User, Tenant
from auth import get_current_user_from_cookie
from core.websocket_manager import manager

router = APIRouter(prefix="/api/v1/hitl", tags=["Human-In-The-Loop"])

class ChallengeCreateRequest(BaseModel):
    booking_task_id: int
    visa_center: str
    appointment_type: Optional[str] = "Long-Term Type D"
    applicant_name: Optional[str] = "Applicant"
    expires_in_seconds: int = 300

class ChallengeSubmitRequest(BaseModel):
    otp_code: str

@router.post("/challenges/create")
def create_challenge(req: ChallengeCreateRequest, db: Session = Depends(get_db)):
    """Called by booking worker when OTP screen is reached."""
    # Check if an active challenge already exists for this task
    existing = db.query(OTPChallenge).filter(
        OTPChallenge.booking_task_id == req.booking_task_id,
        OTPChallenge.status == "PENDING",
        OTPChallenge.expires_at > datetime.utcnow()
    ).first()
    if existing:
        return {
            "challenge_id": existing.challenge_id,
            "status": existing.status,
            "expires_at": existing.expires_at.isoformat(),
            "remaining_seconds": max(0, int((existing.expires_at - datetime.utcnow()).total_seconds()))
        }

    task = db.query(BookingTask).filter(BookingTask.id == req.booking_task_id).first()
    tenant_id = task.tenant_id if task else None
    
    challenge_uuid = f"otp_{uuid.uuid4().hex[:12]}"
    expires_at = datetime.utcnow() + timedelta(seconds=req.expires_in_seconds)
    
    challenge = OTPChallenge(
        challenge_id=challenge_uuid,
        booking_task_id=req.booking_task_id,
        tenant_id=tenant_id,
        applicant_name=req.applicant_name,
        visa_center=req.visa_center,
        appointment_type=req.appointment_type,
        status="PENDING",
        expires_in_seconds=req.expires_in_seconds,
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    
    # 1. Realtime WebSocket Broadcast to open browser dashboard tabs
    try:
        from core.websocket_manager import sync_broadcast
        sync_broadcast({
            "type": "OTP_CHALLENGE_CREATED",
            "challenge_id": challenge.challenge_id,
            "booking_task_id": challenge.booking_task_id,
            "applicant_name": challenge.applicant_name,
            "visa_center": challenge.visa_center,
            "appointment_type": challenge.appointment_type,
            "expires_in_seconds": challenge.expires_in_seconds,
            "expires_at": challenge.expires_at.isoformat()
        })
    except Exception as ws_err:
        print(f"WebSocket broadcast error: {ws_err}")

    # 2. Privacy-safe Web Push notification to PWA (zero applicant/passport data on lockscreen)
    try:
        from notifications import send_push_notification
        user_ids = None
        if tenant_id:
            users = db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).all()
            user_ids = [u.id for u in users]
            
        send_push_notification(
            db=db,
            title="⚠️ Booking Verification Required",
            body="Alamia Copilot: Action needed to finalize visa appointment. Tap to enter code.",
            user_ids=user_ids,
            url=f"/?open_copilot=true&challenge_id={challenge.challenge_id}"
        )
    except Exception as push_err:
        print(f"Web Push dispatch error: {push_err}")
        
    return {
        "challenge_id": challenge.challenge_id,
        "status": challenge.status,
        "expires_at": challenge.expires_at.isoformat(),
        "remaining_seconds": req.expires_in_seconds
    }

@router.get("/challenges/active")
def list_active_challenges(db: Session = Depends(get_db)):
    """Returns currently pending or submitted challenges for the Copilot drawer."""
    now = datetime.utcnow()
    challenges = db.query(OTPChallenge).filter(
        OTPChallenge.status.in_(["PENDING", "SUBMITTED"]),
        OTPChallenge.expires_at > now
    ).order_by(OTPChallenge.created_at.desc()).all()
    
    out = []
    for c in challenges:
        out.append({
            "challenge_id": c.challenge_id,
            "booking_task_id": c.booking_task_id,
            "applicant_name": c.applicant_name or "Applicant",
            "visa_center": c.visa_center or "VAC",
            "appointment_type": c.appointment_type or "Type D",
            "status": c.status,
            "expires_at": c.expires_at.isoformat(),
            "remaining_seconds": max(0, int((c.expires_at - now).total_seconds()))
        })
    return out

@router.get("/challenges/{challenge_id}")
def get_challenge_status(challenge_id: str, db: Session = Depends(get_db)):
    """Called by worker to query/wait for human OTP submission."""
    challenge = db.query(OTPChallenge).filter(OTPChallenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    now = datetime.utcnow()
    if challenge.status == "PENDING" and challenge.expires_at < now:
        challenge.status = "EXPIRED"
        db.commit()
        
    return {
        "challenge_id": challenge.challenge_id,
        "status": challenge.status,
        "otp_code": challenge.otp_code if challenge.status == "SUBMITTED" else None,
        "remaining_seconds": max(0, int((challenge.expires_at - now).total_seconds()))
    }

@router.post("/challenges/{challenge_id}/submit")
def submit_challenge_otp(challenge_id: str, req: ChallengeSubmitRequest, db: Session = Depends(get_db)):
    """Called by staff via Copilot drawer. Pure deterministic fast path (0 LLM)."""
    challenge = db.query(OTPChallenge).filter(OTPChallenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    now = datetime.utcnow()
    if challenge.expires_at < now or challenge.status == "EXPIRED":
        challenge.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=410, detail="OTP challenge has expired")
        
    code = req.otp_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="OTP code cannot be empty")
        
    challenge.otp_code = code
    challenge.status = "SUBMITTED"
    challenge.submitted_at = now
    challenge.submitted_by = "HUMAN_ENTRY"
    
    # Also update booking task otp_code for dual-lookup compatibility
    task = db.query(BookingTask).filter(BookingTask.id == challenge.booking_task_id).first()
    if task:
        task.otp_code = code
        
    db.commit()
    
    # Notify worker via WebSocket
    try:
        from core.websocket_manager import sync_broadcast
        sync_broadcast({
            "type": "OTP_CHALLENGE_SUBMITTED",
            "challenge_id": challenge.challenge_id,
            "booking_task_id": challenge.booking_task_id
        })
    except Exception as ws_err:
        print(f"WebSocket broadcast error: {ws_err}")
        
    return {
        "status": "ok",
        "message": "OTP submitted successfully. Worker will resume booking immediately.",
        "challenge_id": challenge.challenge_id
    }

@router.post("/challenges/{challenge_id}/consume")
def consume_challenge_otp(challenge_id: str, db: Session = Depends(get_db)):
    """Called by worker once it submits OTP to portal. Immediately wipes ephemeral OTP."""
    challenge = db.query(OTPChallenge).filter(OTPChallenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    challenge.status = "CONSUMED"
    challenge.consumed_at = datetime.utcnow()
    challenge.otp_code = None # Privacy purge
    db.commit()
    
    return {"status": "ok", "challenge_id": challenge.challenge_id}
