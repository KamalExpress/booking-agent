from fastapi import APIRouter, Depends, HTTPException, Request, Header, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import secrets
import hashlib
import hmac
import time
from datetime import datetime, timedelta
import uuid
import json

from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount, SystemSetting
from secrets_manager import secrets_manager
# We need to import get_db, but main.py imports routers, so we'll put get_db in a separate module or just depend on models.SessionLocal
from models import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api/v1/worker", tags=["Worker"])

# --- Schemas ---

class RegisterRequest(BaseModel):
    hostname: str
    machine_id: str
    os: str
    cpu: str
    ram: str
    version: str
    location: str
    labels: List[str] = []

class RegisterResponse(BaseModel):
    worker_id: str
    secret: str

class HeartbeatRequest(BaseModel):
    cpu_percent: float
    ram_percent: float
    running_assignments: int

class EventLogRequest(BaseModel):
    assignment_id: Optional[int] = None
    severity: str = "info"
    event_type: str
    payload: Dict[str, Any]

# --- HMAC Authentication Dependency ---

async def verify_worker_hmac(
    request: Request,
    x_worker_id: str = Header(...),
    x_signature: str = Header(...),
    x_timestamp: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Verify HMAC-SHA256 signature from worker.
    Signature = hex(HMAC(secret, timestamp + method + path + body))
    """
    # 1. Prevent replay attacks (timestamp must be within 5 minutes)
    try:
        ts = int(x_timestamp)
        now = int(time.time())
        if abs(now - ts) > 300:
            raise HTTPException(status_code=401, detail="Request expired")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    # 2. Look up worker by ID
    worker = db.query(WorkerNode).filter(WorkerNode.worker_id == x_worker_id).first()
    if not worker or worker.status != "Active":
        raise HTTPException(status_code=401, detail="Worker not found or inactive")
        
    # 3. Reconstruct payload
    body = await request.body()
    payload = f"{x_timestamp}{request.method}{request.url.path}{body.decode('utf-8')}"
    
    # 4. Compute expected HMAC
    # For HMAC to work, we store the raw secret in the database in this architecture (or securely encrypted).
    # Since we need it for validation, we'll store it directly in `secret_hash` (misnamed, but we will use it as plaintext key for now).
    expected_mac = hmac.new(
        worker.secret_hash.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_mac, x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    return worker

# --- Endpoints ---

@router.post("/register", response_model=RegisterResponse)
def register_worker(req: RegisterRequest, db: Session = Depends(get_db)):
    worker_id = f"worker_{uuid.uuid4().hex[:8]}"
    secret = secrets.token_hex(32)
    
    worker = WorkerNode(
        worker_id=worker_id,
        secret_hash=secret, # Storing plaintext to support HMAC
        labels=req.labels,
        version=req.version,
        status="Active",
        last_heartbeat=datetime.utcnow()
    )
    db.add(worker)
    db.commit()
    
    return {"worker_id": worker_id, "secret": secret}

@router.post("/heartbeat")
def worker_heartbeat(
    req: HeartbeatRequest, 
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    worker.last_heartbeat = datetime.utcnow()
    
    # Extend leases owned by this worker
    active_leases = db.query(Lease).filter(Lease.worker_id == worker.worker_id).all()
    for lease in active_leases:
        # Extend lease by 2 minutes from now
        lease.expires_at = datetime.utcnow() + timedelta(minutes=2)
        
    db.commit()
    return {"status": "ok", "extended_leases": len(active_leases)}

@router.get("/assignments/next")
def get_next_assignment(
    response: Response,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    # 1. Clean up expired leases globally
    now = datetime.utcnow()
    expired_leases = db.query(Lease).filter(Lease.expires_at < now).all()
    for lease in expired_leases:
        assignment = db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
        if assignment:
            assignment.status = "Active"
        db.delete(lease)
    if expired_leases:
        db.commit()
        
    # 1.5. Check if THIS worker already has an active lease (e.g. it crashed and restarted)
    existing_lease = db.query(Lease).filter(Lease.worker_id == worker.worker_id).first()
    if existing_lease:
        best_assignment = db.query(Assignment).filter(Assignment.id == existing_lease.assignment_id).first()
        if best_assignment:
            acc = db.query(ScraperAccount).filter(ScraperAccount.id == best_assignment.scraper_account_id).first()
            return {
                "lease_id": existing_lease.id,
                "assignment_id": best_assignment.id,
                "visa_center": best_assignment.visa_center,
                "date_from": best_assignment.date_from,
                "date_to": best_assignment.date_to,
                "scraper_account": {
                    "id": acc.id,
                    "username": acc.username,
                    "password": acc.password,
                    "proxy_string": acc.proxy_string
                } if acc else {}
            }
        
    # 2. Find all active, unleased assignments
    assignments = db.query(Assignment).filter(Assignment.status == "Active").all()
    if not assignments:
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "30"
        return
        
    # 3. Score assignments for this worker
    best_score = -9999
    best_assignment = None
    
    for asm in assignments:
        score = 0
        score += asm.priority * 10
        
        # Check ScraperAccount preferred worker
        acc = db.query(ScraperAccount).filter(ScraperAccount.id == asm.scraper_account_id).first()
        if acc and acc.preferred_worker_id == worker.worker_id:
            score += 100
            
        # Add scoring for labels (e.g. if assignment requires specific labels)
        # Assuming we eventually parse labels, skip for now.
        
        if score > best_score:
            best_score = score
            best_assignment = asm
            
    if not best_assignment:
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "30"
        return
        
    # 4. Create Lease
    lease = Lease(
        assignment_id=best_assignment.id,
        worker_id=worker.worker_id,
        expires_at=datetime.utcnow() + timedelta(minutes=2)
    )
    db.add(lease)
    best_assignment.status = "Leased"
    db.commit()
    db.refresh(lease)
    
    # 5. Return assignment
    acc = db.query(ScraperAccount).filter(ScraperAccount.id == best_assignment.scraper_account_id).first()
    
    return {
        "lease_id": lease.id,
        "assignment_id": best_assignment.id,
        "scraper_account": {
            "id": acc.id,
            "username": acc.username,
            "password": acc.password
        },
        "visa_center": best_assignment.visa_center,
        "date_from": best_assignment.date_from,
        "date_to": best_assignment.date_to,
        "polling_interval": best_assignment.polling_interval
    }

@router.post("/assignments/{assignment_id}/event")
def log_event(
    assignment_id: int,
    req: EventLogRequest,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    log = EventLog(
        source="worker",
        worker_id=worker.worker_id,
        assignment_id=assignment_id,
        severity=req.severity,
        event_type=req.event_type,
        payload=req.payload
    )
    db.add(log)
    
    if req.event_type == "SLOT_FOUND":
        # We would trigger the actual push notification logic here
        pass
        
    db.commit()
    return {"status": "ok"}

@router.get("/runtime-config")
def get_runtime_config(
    request: Request,
    response: Response,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    provider_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.provider").first()
    api_key_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.api_key").first()
    
    provider = provider_setting.value if provider_setting else "capsolver"
    api_key = secrets_manager.decrypt(api_key_setting.encrypted_value) if api_key_setting and api_key_setting.encrypted_value else ""
    
    config_payload = {
        "version": 1,
        "ttl": 1800,
        "captcha": {
            "provider": provider,
            "api_key": api_key
        },
        "worker": {
            "heartbeat_interval": worker.HEARTBEAT_INTERVAL_SECONDS
        },
        "features": {
            "stealth": True,
            "headless": True
        }
    }
    
    config_json = json.dumps(config_payload, sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    
    if_config_hash = request.headers.get("If-Config-Hash")
    if if_config_hash == config_hash:
        response.status_code = 304
        return Response(status_code=304)
        
    config_payload["config_hash"] = config_hash
    return config_payload
