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
from notifications import send_push_notification

from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount, SystemSetting, WorkerVersion
from secrets_manager import secrets_manager
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
    architecture: str
    cpu_cores: Optional[int] = None
    ram: str
    version: str
    chrome_version: Optional[str] = None
    playwright_version: Optional[str] = None
    python_version: Optional[str] = None
    max_concurrency: Optional[int] = 1
    labels: Dict[str, str] = {} # e.g. {"system.os": "windows"}

class RegisterResponse(BaseModel):
    worker_id: str
    secret: str

class HeartbeatRequest(BaseModel):
    cpu_percent: float
    ram_percent: float
    running_assignments: int
    public_ip: Optional[str] = None
    local_ip: Optional[str] = None
    runtime_config_version: Optional[int] = 0

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
    if not worker or worker.scheduling_state == "Disabled":
        raise HTTPException(status_code=401, detail="Worker not found or disabled")
        
    # 3. Reconstruct payload
    body = await request.body()
    payload = f"{x_timestamp}{request.method}{request.url.path}{body.decode('utf-8')}"
    
    # 4. Compute expected HMAC
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
def register_worker(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Enforce minimum version
    wv = db.query(WorkerVersion).filter(WorkerVersion.version == req.version).first()
    if wv and not wv.is_supported:
        raise HTTPException(status_code=400, detail="Worker version is no longer supported.")

    worker_id = f"worker_{uuid.uuid4().hex[:8]}"
    secret = secrets.token_hex(32)
    
    worker = WorkerNode(
        worker_id=worker_id,
        secret_hash=secret,
        labels=req.labels,
        version=req.version,
        observed_ip=request.client.host if request.client else None,
        os=req.os,
        architecture=req.architecture,
        cpu_cores=req.cpu_cores,
        ram=req.ram,
        chrome_version=req.chrome_version,
        playwright_version=req.playwright_version,
        python_version=req.python_version,
        max_concurrency=req.max_concurrency,
        status="Online",
        scheduling_state="Accepting Jobs",
        last_heartbeat=datetime.utcnow()
    )
    db.add(worker)
    db.commit()
    
    return {"worker_id": worker_id, "secret": secret}

@router.post("/heartbeat")
def worker_heartbeat(
    req: HeartbeatRequest, 
    request: Request,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    worker.last_heartbeat = datetime.utcnow()
    worker.public_ip = req.public_ip
    worker.local_ip = req.local_ip
    worker.observed_ip = request.client.host if request.client else worker.observed_ip
    worker.status = "Online"
    worker.current_concurrency = req.running_assignments
    
    # Extend leases owned by this worker
    active_leases = db.query(Lease).filter(Lease.worker_id == worker.worker_id).all()
    for lease in active_leases:
        lease.last_heartbeat = datetime.utcnow()
        lease.expires_at = datetime.utcnow() + timedelta(minutes=2)
        
    # Check if runtime config needs refresh
    saas_version_setting = db.query(SystemSetting).filter(SystemSetting.key == "runtime.config.version").first()
    saas_version = int(saas_version_setting.value) if saas_version_setting and saas_version_setting.value else 1
    refresh = req.runtime_config_version < saas_version
        
    db.commit()
    return {"status": "ok", "extended_leases": len(active_leases), "refresh_runtime_config": refresh}

@router.get("/runtime-config")
def get_runtime_config(worker: WorkerNode = Depends(verify_worker_hmac), db: Session = Depends(get_db)):
    saas_version_setting = db.query(SystemSetting).filter(SystemSetting.key == "runtime.config.version").first()
    saas_version = int(saas_version_setting.value) if saas_version_setting and saas_version_setting.value else 1
    
    captcha_provider = db.query(SystemSetting).filter(SystemSetting.key == "captcha.provider").first()
    captcha_api_key_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.api_key").first()
    
    decrypted_api_key = ""
    if captcha_api_key_setting:
        if captcha_api_key_setting.encrypted_value:
            decrypted_api_key = secrets_manager.decrypt(captcha_api_key_setting.encrypted_value)
        elif captcha_api_key_setting.value:
            decrypted_api_key = captcha_api_key_setting.value
    
    return {
        "version": saas_version,
        "ttl": 1800,
        "captcha": {
            "provider": captcha_provider.value if captcha_provider else "capsolver",
            "api_key": decrypted_api_key
        },
        "proxy": {},
        "browser": {
            "headless": True,
            "launch_timeout": 60000,
            "default_timeout": 30000
        },
        "polling": {
            "interval_seconds": 300
        },
        "feature_flags": {
            "enable_telemetry": True
        },
        "limits": {
            "max_retries": 3
        }
    }

@router.get("/assignments/next")
def get_next_assignment(
    response: Response,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    if worker.scheduling_state != "Accepting Jobs":
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "60"
        return
        
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
                "assignment_context": {
                    "id": best_assignment.id,
                    "visa_center": best_assignment.visa_center,
                    "date_from": best_assignment.date_from,
                    "date_to": best_assignment.date_to
                },
                "scraper_account": {
                    "id": acc.id,
                    "username": acc.username,
                    "password": acc.password,
                    "proxy_string": acc.proxy_string,
                    "proxy_mode": acc.proxy_mode
                } if acc else {},
                "expiry": existing_lease.expires_at.isoformat(),
                "heartbeat_interval": WorkerNode.HEARTBEAT_INTERVAL_SECONDS
            }
        
    # 2. Find all active, unleased assignments
    assignments = db.query(Assignment).filter(Assignment.status == "Active").all()
    
    valid_assignments = []
    for asm in assignments:
        if not asm.last_checked or (now - asm.last_checked).total_seconds() >= asm.polling_interval:
            valid_assignments.append(asm)
            
    if not valid_assignments:
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "30"
        return
        
    # 3. Score assignments for this worker
    best_score = -9999
    best_assignment = None
    
    for asm in valid_assignments:
        # Check required labels
        if asm.required_labels:
            missing_or_mismatch = False
            for k, v in asm.required_labels.items():
                if worker.labels.get(k) != v:
                    missing_or_mismatch = True
                    break
            if missing_or_mismatch:
                continue
                
        score = 0
        score += asm.priority * 10
        
        # Check ScraperAccount preferred worker
        acc = db.query(ScraperAccount).filter(ScraperAccount.id == asm.scraper_account_id).first()
        if acc and acc.preferred_worker_id == worker.worker_id:
            score += 100
            
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
        expires_at=datetime.utcnow() + timedelta(minutes=2),
        status="Leased",
        last_heartbeat=datetime.utcnow()
    )
    db.add(lease)
    best_assignment.status = "Leased"
    db.commit()
    db.refresh(lease)
    
    # 5. Return Lease object
    acc = db.query(ScraperAccount).filter(ScraperAccount.id == best_assignment.scraper_account_id).first()
    
    return {
        "lease_id": lease.id,
        "assignment_context": {
            "id": best_assignment.id,
            "visa_center": best_assignment.visa_center,
            "date_from": best_assignment.date_from,
            "date_to": best_assignment.date_to
        },
        "scraper_account": {
            "id": acc.id,
            "username": acc.username,
            "password": acc.password,
            "proxy_string": acc.proxy_string,
            "proxy_mode": acc.proxy_mode
        } if acc else {},
        "expiry": lease.expires_at.isoformat(),
        "heartbeat_interval": WorkerNode.HEARTBEAT_INTERVAL_SECONDS
    }

@router.post("/assignments/{assignment_id}/complete")
def complete_assignment(
    assignment_id: int,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    lease = db.query(Lease).filter(Lease.assignment_id == assignment_id, Lease.worker_id == worker.worker_id).first()
    if lease:
        lease.status = "Completed"
        db.delete(lease)
        
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment:
        assignment.status = "Active"
        assignment.last_checked = datetime.utcnow()
        
    db.commit()
    return {"status": "ok"}

class StreamLogsRequest(BaseModel):
    logs: list[str]

@router.post("/stream-logs")
def stream_logs(
    req: StreamLogsRequest,
    worker: WorkerNode = Depends(verify_worker_hmac),
):
    import os
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "worker_logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    log_file = os.path.join(logs_dir, f"{worker.worker_id}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        for line in req.logs:
            f.write(line + "\n")
            
    return {"status": "ok"}

@router.post("/logs")
def submit_logs(
    req: EventLogRequest,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    log = EventLog(
        source="worker",
        worker_id=worker.worker_id,
        assignment_id=req.assignment_id,
        severity=req.severity,
        event_type=req.event_type,
        payload=req.payload
    )
    db.add(log)
    
    if req.event_type == "LOGIN_SUCCESS" and req.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == req.assignment_id).first()
        if assignment:
            account = db.query(ScraperAccount).filter(ScraperAccount.id == assignment.scraper_account_id).first()
            if account:
                account.last_login = datetime.utcnow()
                send_push_notification(db, "Login Successful", f"Worker successfully logged into {account.username} (Center {assignment.visa_center})")
                
    elif req.event_type == "NO_SLOTS_FOUND":
        friendly_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        send_push_notification(db, "Slot Monitor", f"No Slots available; last checked: {friendly_time}")
        
    elif req.event_type == "SLOT_FOUND":
        send_push_notification(db, "Slots Found!", "Slots are available; you can try booking now!")
        
        # Pause ALL active assignments to stop wasting captcha tokens
        active_assignments = db.query(Assignment).filter(Assignment.status.in_(["Active", "Leased"])).all()
        for asm in active_assignments:
            asm.status = "Paused"
            
        # Clean up any active leases for these assignments so workers drop them
        if active_assignments:
            assignment_ids = [a.id for a in active_assignments]
            db.query(Lease).filter(Lease.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)

    db.commit()
    return {"status": "ok"}
