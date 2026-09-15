import os
import json
import inspect
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, name: str):
            self.name = name
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def sse_app(self, prefix: str = "/mcp"):
            from starlette.applications import Starlette
            from starlette.responses import JSONResponse
            from starlette.routing import Route

            async def handle_list(request):
                return JSONResponse({"tools": list(self._tools.keys())})

            return Starlette(routes=[Route("/tools", handle_list, methods=["GET"])])

from sqlalchemy.orm import Session
from models import SessionLocal, WorkerNode, Lease, WaitlistQueue, BookingTask, PortalAccount, Proxy, EventLog, Assignment, SystemSetting
from services.lease_service import LeaseService
import services.travelos_capabilities as caps

mcp = FastMCP("KESaaSAdmin")

# ---------------------------------------------------------------------------
# Core Fleet & System Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_workers() -> str:
    """Get a list of all registered workers and their status."""
    return caps.get_workers()

@mcp.tool()
def get_worker_details(worker_id: str) -> str:
    """Inspect detailed status, active lease, and assignment context for a specific worker."""
    return caps.get_worker_details(worker_id=worker_id)

@mcp.tool()
def get_worker_logs(worker_id: str, limit: int = 10, since_minutes: int = 15, until_minutes: int = 0) -> str:
    """Fetch recent log events, errors, and actions for a specific worker within optional time boundaries."""
    return caps.get_worker_logs(worker_id=worker_id, limit=limit, since_minutes=since_minutes, until_minutes=until_minutes)

@mcp.tool()
def get_available_slots(visa_center: str = "", portal: str = "", days: int = 7, limit: int = 10) -> str:
    """Retrieve active open appointment slots or recent historical slots discovered by scraping workers."""
    return caps.get_available_slots(visa_center=visa_center, portal=portal, days=days, limit=limit)

@mcp.tool()
def get_proxy_health() -> str:
    """Inspect proxy pool health, active connections, and cooldown states."""
    return caps.get_proxy_health()

@mcp.tool()
def get_active_leases(limit: int = 20) -> str:
    """List all currently active or pending worker leases with associated accounts and proxies."""
    return caps.get_active_leases(limit=limit)

@mcp.tool()
def unlease_resource(resource_type: str, resource_id: int) -> str:
    """Forcefully unlock a stuck resource (resource_type: 'account', 'proxy', or 'lease') back to READY."""
    return caps.unlease_resource(resource_type=resource_type, resource_id=resource_id)

@mcp.tool()
def get_portal_health_summary(portal: str = "") -> str:
    """Get comprehensive system and portal health diagnostics, worker errors, and actionable recommendations."""
    return caps.get_portal_health_summary(portal=portal)

@mcp.tool()
def trigger_maintenance_cycle() -> str:
    """Trigger the orphan resource reconciliation and lease cleanup routine immediately."""
    return caps.trigger_maintenance_cycle()

# ---------------------------------------------------------------------------
# Dedicated Autonomous Watchdog MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def watchdog_get_system_topology() -> str:
    """Get complete real-time pipeline status across workers, assignments, waitlist queue, active tasks, and accounts."""
    db: Session = SessionLocal()
    try:
        lease_svc = LeaseService(db)
        lease_svc.expire_stale_leases()

        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=WorkerNode.WORKER_TIMEOUT_SECONDS)

        workers = db.query(WorkerNode).all()
        online_scrapers = [w.worker_id for w in workers if w.can_scrape and w.last_heartbeat and w.last_heartbeat >= cutoff]
        online_bookers = [w.worker_id for w in workers if w.can_book and w.last_heartbeat and w.last_heartbeat >= cutoff]

        assignments = db.query(Assignment).all()
        asms_data = []
        for a in assignments:
            is_due = not a.last_checked or (now - a.last_checked).total_seconds() >= a.polling_interval
            asms_data.append({
                "center": a.visa_center,
                "status": a.status,
                "interval": a.polling_interval,
                "is_due_now": is_due
            })

        queue_entries = db.query(WaitlistQueue).all()
        q_counts = {"PENDING": 0, "DISPATCHED": 0, "PROCESSING": 0, "BOOKED": 0, "FAILED": 0, "CANCELLED": 0}
        for q in queue_entries:
            st = q.status or "PENDING"
            q_counts[st] = q_counts.get(st, 0) + 1

        active_leases = db.query(Lease).filter(Lease.status.in_(["Leased", "Running"])).count()

        summary = {
            "timestamp": now.isoformat(),
            "workers": {
                "scrapers_online": online_scrapers,
                "bookers_online": online_bookers,
                "total": len(workers)
            },
            "assignments": asms_data,
            "waitlist_queue": q_counts,
            "active_leases_count": active_leases
        }
        return json.dumps(summary, indent=2)
    finally:
        db.close()

@mcp.tool()
def watchdog_diagnose_pipeline() -> str:
    """Analyze the pipeline for stalls, starvation, orphan leases, and configuration blockers."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=WorkerNode.WORKER_TIMEOUT_SECONDS)
        anomalies = []

        workers = db.query(WorkerNode).all()
        online_scrapers = sum(1 for w in workers if w.can_scrape and w.last_heartbeat and w.last_heartbeat >= cutoff)
        online_bookers = sum(1 for w in workers if w.can_book and w.last_heartbeat and w.last_heartbeat >= cutoff)
        
        pending_queue = db.query(WaitlistQueue).filter(WaitlistQueue.status.in_(["PENDING", "WAITING"])).count()
        dispatched_queue = db.query(WaitlistQueue).filter(WaitlistQueue.status == "DISPATCHED").count()

        if (pending_queue > 0 or dispatched_queue > 0) and online_scrapers == 0:
            anomalies.append({
                "severity": "CRITICAL",
                "issue": "Scraper Fleet Starvation",
                "detail": f"{pending_queue} items waiting in queue, but 0 scraper workers are online.",
                "suggested_action": "Start scraper worker node (can_scrape=True)."
            })

        if dispatched_queue > 0 and online_bookers == 0:
            anomalies.append({
                "severity": "CRITICAL",
                "issue": "Booker Fleet Starvation",
                "detail": f"{dispatched_queue} items in DISPATCHED state, but 0 booker workers are online.",
                "suggested_action": "Start booker worker node (can_book=True) or reset stuck queue."
            })

        stalled_tasks = db.query(BookingTask).filter(
            BookingTask.status == "PENDING",
            BookingTask.active_status == True,
            BookingTask.created_at < (now - timedelta(seconds=30))
        ).all()
        for t in stalled_tasks:
            anomalies.append({
                "severity": "WARNING",
                "issue": f"Stalled Task #{t.id}",
                "detail": f"Task created {(now - t.created_at).total_seconds():.0f}s ago for Applicant #{t.applicant_id} has not been claimed.",
                "suggested_action": "Execute watchdog_reset_queue() to return applicant to WAITING."
            })

        ready_accounts = db.query(PortalAccount).filter(PortalAccount.status == "READY", PortalAccount.is_locked == False).count()
        cooldown_accounts = db.query(PortalAccount).filter(PortalAccount.status == "COOLDOWN").count()
        if ready_accounts == 0 and cooldown_accounts > 0:
            anomalies.append({
                "severity": "WARNING",
                "issue": "Portal Account Lock Deadlock",
                "detail": f"0 READY accounts available ({cooldown_accounts} in COOLDOWN).",
                "suggested_action": "Execute watchdog_reset_cooldowns() to unfreeze accounts."
            })

        status = "HEALTHY" if not anomalies else ("CRITICAL" if any(a["severity"] == "CRITICAL" for a in anomalies) else "DEGRADED")
        return json.dumps({"status": status, "anomalies": anomalies, "checked_at": now.isoformat()}, indent=2)
    finally:
        db.close()

@mcp.tool()
def watchdog_trigger_poll(visa_center: str = "") -> str:
    """Surge monitoring assignments to poll the visa center portal immediately."""
    db: Session = SessionLocal()
    try:
        query = db.query(Assignment)
        if visa_center:
            query = query.filter(Assignment.visa_center == visa_center)
        assignments = query.all()
        past = datetime.utcnow() - timedelta(hours=1)
        for a in assignments:
            if a.status == "Paused":
                a.status = "Active"
            a.last_checked = past
        db.commit()
        return f"Surged immediate polling for {len(assignments)} assignment(s)."
    finally:
        db.close()

@mcp.tool()
def watchdog_reset_queue() -> str:
    """Self-heal orphan leases, cancel dead booking tasks, and reset non-booked queue entries back to WAITING."""
    db: Session = SessionLocal()
    try:
        lease_svc = LeaseService(db)
        lease_svc.expire_stale_leases()

        entries = db.query(WaitlistQueue).filter(WaitlistQueue.status.in_(["DISPATCHED", "PROCESSING", "FAILED"])).all()
        for e in entries:
            e.status = "PENDING"
            db.query(BookingTask).filter(
                BookingTask.applicant_id == e.applicant_id,
                BookingTask.status.in_(["PENDING", "FAILED"])
            ).update({"status": "FAILED", "active_status": False})
        db.commit()
        return f"Successfully self-healed and reset {len(entries)} queue entries to PENDING/WAITING."
    finally:
        db.close()

@mcp.tool()
def watchdog_reset_cooldowns() -> str:
    """Immediately unfreeze all portal accounts and proxies currently in COOLDOWN."""
    db: Session = SessionLocal()
    try:
        accs = db.query(PortalAccount).filter(PortalAccount.status == "COOLDOWN").update({"status": "READY", "cooldown_until": None})
        prxs = db.query(Proxy).filter(Proxy.status == "COOLDOWN").update({"status": "READY", "cooldown_until": None, "failure_count": 0})
        db.commit()
        return f"Reset cooldown for {accs} portal accounts and {prxs} proxies."
    finally:
        db.close()

@mcp.tool()
def watchdog_inject_otp(task_id: int, otp_code: str) -> str:
    """Inject a captured OTP / SMS verification code into an in-flight booking task."""
    db: Session = SessionLocal()
    try:
        task = db.query(BookingTask).filter(BookingTask.id == task_id).first()
        if not task:
            return f"BookingTask #{task_id} not found."
        
        task.otp_code = str(otp_code)
        db.add(EventLog(
            source="watchdog_mcp",
            assignment_id=task.assignment_id,
            event_type="OTP_RECEIVED",
            severity="info",
            payload={"task_id": task.id, "extracted_otp": str(otp_code)}
        ))
        db.commit()
        return f"Injected OTP '{otp_code}' into BookingTask #{task_id}."
    finally:
        db.close()
