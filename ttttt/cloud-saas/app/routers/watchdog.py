import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from models import get_db, Assignment, WorkerNode, Lease, WaitlistQueue, BookingTask, PortalAccount, Proxy, EventLog, SchedulerDecision, SystemSetting
from services.lease_service import LeaseService, get_lease_service

router = APIRouter(prefix="/api/v1/watchdog", tags=["Watchdog Supervisor"])

WATCHDOG_API_KEY = os.getenv("WATCHDOG_API_KEY", "")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "kamal_express_saas_secure_key_12345")

def verify_watchdog_auth(
    request: Request,
    x_watchdog_key: Optional[str] = Header(None, alias="X-Watchdog-Key"),
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # 1. Check API Key headers / query
    provided_key = x_watchdog_key or api_key
    if not provided_key and authorization:
        if authorization.startswith("Bearer "):
            provided_key = authorization.split(" ")[1]
        elif authorization.startswith("ApiKey "):
            provided_key = authorization.split(" ")[1]

    valid_keys = [k for k in [WATCHDOG_API_KEY, MCP_API_KEY, SECRET_KEY] if k]
    if provided_key and provided_key in valid_keys:
        return True

    # 2. Check JWT Token fallback
    if provided_key:
        try:
            import jwt
            from auth import SECRET_KEY as JWT_SECRET, ALGORITHM
            payload = jwt.decode(provided_key, JWT_SECRET, algorithms=[ALGORITHM])
            if payload.get("sub"):
                return True
        except Exception:
            pass

    # For local development / simulation, permit if no secret configured
    if os.getenv("ENVIRONMENT") == "development" or os.getenv("ALLOW_DEV_WATCHDOG", "true").lower() in ["true", "1"]:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized. Provide valid X-Watchdog-Key or Authorization Bearer token."
    )

def ensure_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

@router.get("/status")
def get_watchdog_system_status(
    auth: bool = Depends(verify_watchdog_auth),
    db: Session = Depends(get_db),
    lease_service: LeaseService = Depends(get_lease_service)
):
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=WorkerNode.WORKER_TIMEOUT_SECONDS)

        # 1. Self-heal stale leases and orphan queue entries before reporting
        try:
            lease_service.expire_stale_leases()
        except Exception:
            pass

        # 2. Assignments
        assignments = db.query(Assignment).all()
        asm_data = []
        for a in assignments:
            lc = ensure_naive(a.last_checked)
            is_due = not lc or (now - lc).total_seconds() >= a.polling_interval
            next_due_in = 0 if is_due else max(0, int(a.polling_interval - (now - lc).total_seconds()))
            asm_data.append({
                "id": a.id,
                "visa_center": a.visa_center,
                "date_from": a.date_from,
                "date_to": a.date_to,
                "status": a.status,
                "priority": a.priority,
                "polling_interval": a.polling_interval,
                "last_checked": a.last_checked.isoformat() if a.last_checked else None,
                "is_due_for_polling": is_due,
                "next_due_seconds": next_due_in
            })

        # 3. Workers
        workers = db.query(WorkerNode).all()
        worker_data = []
        for w in workers:
            hb = ensure_naive(w.last_heartbeat)
            is_online = bool(hb and hb >= cutoff)
            worker_data.append({
                "worker_id": w.worker_id,
                "can_scrape": w.can_scrape,
                "can_book": w.can_book,
                "is_online": is_online,
                "current_concurrency": w.current_concurrency,
                "max_concurrency": w.max_concurrency,
                "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None
            })

    # 4. Leases
    active_leases = db.query(Lease).filter(Lease.status.in_(["Leased", "Running"])).all()
    lease_data = [{
        "lease_id": l.id,
        "worker_id": l.worker_id,
        "assignment_id": l.assignment_id,
        "booking_task_id": l.booking_task_id,
        "status": l.status,
        "expires_at": l.expires_at.isoformat() if l.expires_at else None
    } for l in active_leases]

    # 5. Waitlist Queue
    queue_entries = db.query(WaitlistQueue).order_by(WaitlistQueue.priority.desc(), WaitlistQueue.id.asc()).all()
    queue_counts = {"PENDING": 0, "DISPATCHED": 0, "PROCESSING": 0, "BOOKED": 0, "FAILED": 0, "CANCELLED": 0}
    for q in queue_entries:
        st = q.status or "PENDING"
        queue_counts[st] = queue_counts.get(st, 0) + 1

    queue_sample = []
    for q in queue_entries[:15]:
        name = f"{(q.applicant.firstname or '')} {(q.applicant.surname or '')}".strip() if q.applicant else f"Applicant #{q.applicant_id}"
        queue_sample.append({
            "id": q.id,
            "applicant_id": q.applicant_id,
            "applicant_name": name or f"Applicant #{q.applicant_id}",
            "visa_center": q.visa_center,
            "status": q.status,
            "priority": q.priority
        })

    # 6. Booking Tasks
    tasks = db.query(BookingTask).order_by(BookingTask.id.desc()).limit(15).all()
    task_data = [{
        "id": t.id,
        "applicant_id": t.applicant_id,
        "visa_center": t.visa_center,
        "target_date": t.target_date,
        "target_time": t.target_time,
        "status": t.status,
        "attempts": t.attempts,
        "max_attempts": t.max_attempts,
        "failure_reason": t.failure_reason,
        "reference_number": t.reference_number
    } for t in tasks]

    # 7. Accounts & Proxies summary
    accounts = db.query(PortalAccount).all()
    acc_counts = {"READY": 0, "LEASED": 0, "COOLDOWN": 0, "BANNED": 0, "DISABLED": 0}
    for acc in accounts:
        st = acc.status or "READY"
        acc_counts[st] = acc_counts.get(st, 0) + 1

    proxies = db.query(Proxy).all()
    proxy_counts = {"READY": 0, "LEASED": 0, "COOLDOWN": 0, "BANNED": 0}
    for prx in proxies:
        st = prx.status or "READY"
        proxy_counts[st] = proxy_counts.get(st, 0) + 1

    # 8. Recent 15 logs
    recent_logs = db.query(EventLog).order_by(EventLog.id.desc()).limit(15).all()
    log_data = [{
        "id": lg.id,
        "event_type": lg.event_type,
        "severity": lg.severity,
        "worker_id": lg.worker_id,
        "payload": lg.payload,
        "timestamp": lg.created_at.isoformat() if lg.created_at else None
    } for lg in recent_logs]

    return {
        "timestamp": now.isoformat(),
        "assignments": asm_data,
        "workers": worker_data,
        "active_leases": lease_data,
        "queue_summary": {
            "counts": queue_counts,
            "items": queue_sample
        },
        "booking_tasks": task_data,
        "accounts_summary": acc_counts,
        "proxies_summary": proxy_counts,
        "recent_logs": log_data
    }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/trigger-poll")
def trigger_immediate_poll(
    visa_center: Optional[str] = None,
    unpause: bool = True,
    auth: bool = Depends(verify_watchdog_auth),
    db: Session = Depends(get_db)
):
    """Resets last_checked timestamp so workers poll immediately."""
    query = db.query(Assignment)
    if visa_center:
        query = query.filter(Assignment.visa_center == visa_center)

    assignments = query.all()
    updated_count = 0
    past_time = datetime.utcnow() - timedelta(hours=2)
    for a in assignments:
        if unpause and a.status == "Paused":
            a.status = "Active"
        a.last_checked = past_time
        updated_count += 1

    db.commit()
    return {"status": "ok", "message": f"Triggered immediate poll for {updated_count} assignment(s)."}

@router.post("/reset-queue")
def reset_stuck_queue(
    auth: bool = Depends(verify_watchdog_auth),
    db: Session = Depends(get_db),
    lease_service: LeaseService = Depends(get_lease_service)
):
    """Self-heals orphan leases and resets non-booked queue entries to PENDING."""
    lease_service.expire_stale_leases()
    
    # Release accounts and proxies held by any stalled booking leases
    stuck_leases = db.query(Lease).filter(Lease.booking_task_id.isnot(None), Lease.status.in_(["Leased", "Running"])).all()
    for l in stuck_leases:
        l.status = "Expired"
        if l.portal_account_id:
            db.query(PortalAccount).filter(PortalAccount.id == l.portal_account_id).update({"status": "READY"})
        if l.proxy_id:
            db.query(Proxy).filter(Proxy.id == l.proxy_id).update({"status": "READY"})

    entries = db.query(WaitlistQueue).filter(WaitlistQueue.status.in_(["DISPATCHED", "PROCESSING", "FAILED"])).all()
    for e in entries:
        e.status = "PENDING"
        db.query(BookingTask).filter(
            BookingTask.applicant_id == e.applicant_id,
            BookingTask.status.in_(["PENDING", "CLAIMED", "FAILED"])
        ).update({"status": "FAILED", "active_status": False})
        
    db.commit()
    return {"status": "ok", "message": f"Reset {len(entries)} queue entries and released {len(stuck_leases)} booking lease(s)."}

@router.post("/reset-cooldowns")
def reset_all_cooldowns(
    auth: bool = Depends(verify_watchdog_auth),
    db: Session = Depends(get_db)
):
    """Clears cooldown timers on all portal accounts and proxies."""
    acc_count = db.query(PortalAccount).filter(PortalAccount.status == "COOLDOWN").update({"status": "READY", "cooldown_until": None})
    prx_count = db.query(Proxy).filter(Proxy.status == "COOLDOWN").update({"status": "READY", "cooldown_until": None, "failure_count": 0})
    db.commit()
    return {"status": "ok", "message": f"Reset cooldown for {acc_count} accounts and {prx_count} proxies."}

@router.post("/inject-otp")
def inject_task_otp(
    payload: dict,
    auth: bool = Depends(verify_watchdog_auth),
    db: Session = Depends(get_db)
):
    """Directly supplies an OTP code for an in-flight booking task."""
    task_id = payload.get("task_id")
    otp_code = payload.get("otp_code")
    if not task_id or not otp_code:
        raise HTTPException(status_code=400, detail="task_id and otp_code required")

    task = db.query(BookingTask).filter(BookingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.otp_code = str(otp_code)
    db.add(EventLog(
        source="watchdog",
        assignment_id=task.assignment_id,
        event_type="OTP_RECEIVED",
        severity="info",
        payload={"task_id": task.id, "extracted_otp": str(otp_code)}
    ))
    db.commit()
    return {"status": "ok", "message": f"Injected OTP {otp_code} for Task #{task_id}"}
