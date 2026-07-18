from fastapi import APIRouter, Depends, HTTPException, Request, Header, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
import secrets
import hashlib
import hmac
import time
from datetime import datetime, timedelta
import uuid
import json
from notifications import send_push_notification

from models import WorkerNode, Assignment, Lease, EventLog, PortalAccount, SystemSetting, WorkerVersion, WorkerLog
from secrets_manager import secrets_manager
from models import SessionLocal

from services.worker_service import WorkerService, get_worker_service
from services.lease_service import LeaseService, get_lease_service
from services.maintenance_service import MaintenanceService, get_maintenance_service
from services.scheduler_service import SchedulerService

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

class WorkerLogRequest(BaseModel):
    assignment_id: Optional[int] = None
    payload: Union[Dict[str, Any], List[Any]]

class StreamLogsRequest(BaseModel):
    logs: list[str]

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
def register_worker(
    req: RegisterRequest, 
    request: Request, 
    worker_service: WorkerService = Depends(get_worker_service)
):
    try:
        worker_id, secret = worker_service.register_worker(req, request.client.host if request.client else None)
        return {"worker_id": worker_id, "secret": secret}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/heartbeat")
def worker_heartbeat(
    req: HeartbeatRequest, 
    request: Request,
    worker: WorkerNode = Depends(verify_worker_hmac),
    worker_service: WorkerService = Depends(get_worker_service),
    lease_service: LeaseService = Depends(get_lease_service)
):
    refresh_config = worker_service.process_heartbeat(worker, req, request.client.host if request.client else None)
    extended_count = lease_service.extend_worker_leases(worker.worker_id)
    return {"status": "ok", "extended_leases": extended_count, "refresh_runtime_config": refresh_config}

@router.post("/offline")
def worker_offline(
    worker: WorkerNode = Depends(verify_worker_hmac),
    worker_service: WorkerService = Depends(get_worker_service)
):
    worker_service.mark_worker_offline(worker.worker_id)
    return {"status": "ok"}

@router.get("/runtime-config")
def get_runtime_config(
    worker: WorkerNode = Depends(verify_worker_hmac), 
    worker_service: WorkerService = Depends(get_worker_service)
):
    return worker_service.get_runtime_config()

@router.get("/assignments/next")
def get_next_assignment(
    response: Response,
    worker: WorkerNode = Depends(verify_worker_hmac),
    lease_service: LeaseService = Depends(get_lease_service),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
    db: Session = Depends(get_db)
):
    # 0. Run defensive cleanup cycle
    maintenance_service.run_cleanup_cycle()
    
    if worker.scheduling_state != "Accepting Jobs":
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "60"
        return
        
    # 1. Clean up expired leases globally
    lease_service.expire_stale_leases()
        
    # 1.5. Check if THIS worker already has an active lease (e.g. it crashed and restarted)
    existing_lease = lease_service.get_existing_lease_for_worker(worker)
    if existing_lease:
        return existing_lease
        
    # 2 & 3 & 4. Find next assignment and create lease
    scheduler = SchedulerService(db)
    next_lease = scheduler.get_next_lease(worker.worker_id)
    if not next_lease:
        response.status_code = status.HTTP_204_NO_CONTENT
        response.headers["Retry-After"] = "30"
        return
        
    return next_lease

@router.post("/assignments/{assignment_id}/complete")
def complete_assignment(
    assignment_id: int,
    worker: WorkerNode = Depends(verify_worker_hmac),
    lease_service: LeaseService = Depends(get_lease_service)
):
    lease_service.complete_lease(worker.worker_id, assignment_id)
    return {"status": "ok"}

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
    db: Session = Depends(get_db),
    lease_service: LeaseService = Depends(get_lease_service)
):
    scheduler = SchedulerService(db)
    
    if req.assignment_id:
        lease = db.query(Lease).filter(
            Lease.worker_id == worker.worker_id, 
            Lease.assignment_id == req.assignment_id
        ).first()
        if lease:
            scheduler.handle_event(req.event_type, lease, req.payload)

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
        if assignment and 'lease' in locals() and lease:
            account = db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
            if account:
                account.last_login = datetime.utcnow()
                notify_login = db.query(SystemSetting).filter(SystemSetting.key == "notify.login_success").first()
                if not notify_login or notify_login.value == "true":
                    send_push_notification(db, "Login Successful", f"Worker successfully logged into {account.username} (Center {assignment.visa_center})", visa_center_id=assignment.visa_center)
                
    elif req.event_type == "NO_SLOTS_FOUND":
        notify_no_slots = db.query(SystemSetting).filter(SystemSetting.key == "notify.no_slots_found").first()
        vac_id = req.payload.get("visa_center") if req.payload else None
        if not notify_no_slots or notify_no_slots.value == "true":
            friendly_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            send_push_notification(db, "Slot Monitor", f"No Slots available; last checked: {friendly_time}", visa_center_id=vac_id)
        
    elif req.event_type == "SLOT_FOUND":
        # Extract slot information
        target_date = "Unknown Date"
        slot_count = 0
        vac_id = "Unknown Center"
        start_time_str = ""
        app_type = ""
        
        if req.payload:
            target_date = req.payload.get("date", target_date)
            vac_id = req.payload.get("visa_center", vac_id)
            if "slots" in req.payload and isinstance(req.payload["slots"], list):
                slots = req.payload["slots"]
                slot_count = len(slots)
                if slots and "starttime" in slots[0]:
                    try:
                        from datetime import datetime
                        time_obj = datetime.strptime(slots[0]['starttime'], "%H:%M")
                        start_time_str = f" at {time_obj.strftime('%I:%M %p')}"
                    except:
                        start_time_str = f" at {slots[0]['starttime']}"
        
        if req.assignment_id:
            assignment = db.query(Assignment).filter(Assignment.id == req.assignment_id).first()
            if assignment:
                # Save to SlotAvailability database using the vac_id from the worker payload
                from models import SlotAvailability, BookingTask
                availability = SlotAvailability(
                    assignment_id=assignment.id,
                    visa_center=vac_id,
                    date=target_date,
                    slots_data=req.payload.get("slots", []) if req.payload else [],
                    found_by=worker.worker_id
                )
                db.add(availability)
                
                # Event-driven Deduplication & Booking Pipeline
                if slot_count > 0 and "slots" in req.payload:
                    for slot in req.payload["slots"]:
                        slot_time = slot.get("starttime", "00:00")
                        try:
                            bt = BookingTask(
                                assignment_id=assignment.id,
                                provider=assignment.provider,
                                visa_center=vac_id,
                                target_date=target_date,
                                target_time=slot_time,
                                slot_payload=slot,
                                priority=10,
                                expires_at=datetime.utcnow() + timedelta(hours=2)
                            )
                            db.add(bt)
                            db.commit() # This will fail if duplicate due to UniqueConstraint
                        except Exception as e:
                            # IntegrityError: Duplicate booking task ignored
                            db.rollback()
                            continue
                
        # Resolve center name and type string from global config
        center_name = f"Center {vac_id}"
        type_str = ""
        vc_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.visa_centers_config").first()
        if vc_setting and vc_setting.value:
            for center_str in vc_setting.value.split(","):
                parts = center_str.strip().split(":")
                if len(parts) >= 3 and parts[0] == vac_id:
                    center_name = f"{parts[2]} Visa Center"
                    app_type = parts[1]
                    if app_type == "26": type_str = " for Type D Long Stay"
                    elif app_type == "6": type_str = " for National Visa"
                    elif app_type == "2": type_str = " for Legalization"
                    elif app_type == "0": type_str = " for Standard"
                    else: type_str = f" for Type {app_type}"
                    break
        
        push_message = f"{slot_count} Slot{'s' if slot_count != 1 else ''} found on {target_date}{start_time_str} - {center_name}{type_str}"
        
        notify_slots = db.query(SystemSetting).filter(SystemSetting.key == "notify.slots_found").first()
        if not notify_slots or notify_slots.value == "true":
            send_push_notification(db, "Slots Found!", push_message, visa_center_id=vac_id)
        
        # Pause ALL active assignments to stop wasting captcha tokens
        active_assignments = db.query(Assignment).filter(Assignment.status.in_(["Active", "Leased"])).all()
        for asm in active_assignments:
            asm.status = "Paused"
            
        # Clean up any active leases for these assignments so workers drop them
        if active_assignments:
            assignment_ids = [a.id for a in active_assignments]
            lease_service.cancel_active_leases(assignment_ids)

    db.commit()
    return {"status": "ok"}

@router.post("/worker-logs")
def submit_worker_logs(
    req: WorkerLogRequest,
    worker: WorkerNode = Depends(verify_worker_hmac),
    db: Session = Depends(get_db)
):
    """Endpoint for headless workers to upload their captured HTTP request/response logs."""
    log = WorkerLog(
        worker_id=worker.worker_id,
        assignment_id=req.assignment_id,
        payload=req.payload
    )
    db.add(log)
    db.commit()
    return {"status": "ok", "log_id": log.id}
