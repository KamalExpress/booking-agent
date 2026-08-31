"""
TravelOS Unified Capabilities Layer.
This module defines read-only operational functions directly querying the database.
Both the TravelOS FastMCP Server and TravelOS Copilot Agent Loop consume these tools.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import json

from models import SessionLocal, WorkerNode, SlotAvailability, Proxy, PortalAccount, Lease, Assignment, EventLog, WorkerLog, PushSubscription

def format_human_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds into clean human-readable relative time."""
    if seconds is None:
        return "N/A"
    sec = int(max(0, seconds))
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        m = sec // 60
        s = sec % 60
        return f"{m}m {s}s" if s > 0 else f"{m}m"
    elif sec < 86400:
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        d = sec // 86400
        h = (sec % 86400) // 3600
        return f"{d}d {h}h" if h > 0 else f"{d}d"

def format_human_age(seconds: Optional[float]) -> str:
    """Format age into clean relative string."""
    d = format_human_duration(seconds)
    return "N/A" if d == "N/A" else f"{d} ago"

# ---------------------------------------------------------------------------
# 1. Worker Capabilities
# ---------------------------------------------------------------------------

def get_workers(db: Optional[Session] = None) -> str:
    """Get an overview of all registered workers, states, and heartbeats."""
    sdb = db or SessionLocal()
    try:
        workers = sdb.query(WorkerNode).filter(WorkerNode.is_archived == False).all()
        if not workers:
            return "No registered workers found in the system."
        
        lines = [f"Total Workers: {len(workers)}"]
        for w in workers:
            hb_age = (datetime.utcnow() - w.last_heartbeat).total_seconds() if getattr(w, 'last_heartbeat', None) else None
            status = getattr(w, 'status', 'Offline') or 'Offline'
            sched = getattr(w, 'scheduling_state', 'Accepting Jobs') or 'Accepting Jobs'
            lines.append(f"- {w.worker_id} [{status}] ({sched}) - Scrape: {w.can_scrape}, Book: {w.can_book} - Last Heartbeat: {format_human_age(hb_age)}")
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


def get_worker_details(worker_id: str, db: Optional[Session] = None) -> str:
    """Inspect detailed status, active lease, and assignment context for a specific worker."""
    sdb = db or SessionLocal()
    try:
        worker = sdb.query(WorkerNode).filter(WorkerNode.worker_id == str(worker_id).strip()).first()
        if not worker:
            return f"Worker '{worker_id}' not found."
        
        hb_age = (datetime.utcnow() - worker.last_heartbeat).total_seconds() if getattr(worker, 'last_heartbeat', None) else None
        lines = [
            f"Worker: {worker.worker_id}",
            f"Status: {getattr(worker, 'status', 'Offline')}",
            f"Scheduling State: {getattr(worker, 'scheduling_state', 'Accepting Jobs')}",
            f"Last Heartbeat: {format_human_age(hb_age)} ({worker.last_heartbeat})",
            f"Concurrency: {worker.current_concurrency}/{worker.max_concurrency}",
            f"Capabilities: Scrape={worker.can_scrape}, Book={worker.can_book}",
            f"Observed IP: {worker.observed_ip or 'Unknown'}"
        ]
        
        # Check active lease
        lease = sdb.query(Lease).filter(
            Lease.worker_id == worker.worker_id,
            Lease.status.in_(["Leased", "Running", "Pending"])
        ).first()
        
        if lease:
            asg = sdb.query(Assignment).filter(Assignment.id == lease.assignment_id).first() if lease.assignment_id else None
            vac = asg.visa_center if asg else "N/A"
            lines.append(f"Current Lease: #{lease.id} ({lease.status}) on VAC {vac} (Expires: {lease.expires_at})")
        else:
            lines.append("Current Lease: None (Idle)")
            
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


def get_worker_logs(worker_id: str, limit: int = 5, db: Optional[Session] = None) -> str:
    """Fetch recent log events, errors, and actions for a specific worker."""
    sdb = db or SessionLocal()
    try:
        w_id = str(worker_id).strip()
        events = sdb.query(EventLog).filter(EventLog.worker_id == w_id).order_by(EventLog.created_at.desc()).limit(limit).all()
        
        if not events:
            # Fallback to WorkerLog table
            wlogs = sdb.query(WorkerLog).filter(WorkerLog.worker_id == w_id).order_by(WorkerLog.created_at.desc()).limit(limit).all()
            if not wlogs:
                return f"No recent logs found for worker '{w_id}'."
            lines = [f"Recent logs for {w_id}:"]
            for l in wlogs:
                lines.append(f"[{l.created_at.strftime('%H:%M:%S')}] {l.message}")
            return "\n".join(lines)
            
        lines = [f"Recent events for {w_id}:"]
        for ev in events:
            payload_str = str(ev.payload)[:100] if ev.payload else ""
            lines.append(f"[{ev.created_at.strftime('%H:%M:%S')}] {ev.event_type} - {payload_str}")
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


# ---------------------------------------------------------------------------
# 2. Slots Capabilities
# ---------------------------------------------------------------------------

def get_available_slots(visa_center: Optional[str] = None, days: Optional[int] = 7, limit: int = 10, db: Optional[Session] = None) -> str:
    """Retrieve active open appointment slots or recent historical slots discovered by scraping workers."""
    sdb = db or SessionLocal()
    try:
        from datetime import timedelta
        # 1. Check active open slots
        active_query = sdb.query(SlotAvailability).filter(
            SlotAvailability.status == "AVAILABLE",
            SlotAvailability.is_archived == False
        )
        if visa_center and str(visa_center).strip():
            active_query = active_query.filter(SlotAvailability.visa_center.ilike(f"%{str(visa_center).strip()}%"))
            
        active_slots = active_query.order_by(SlotAvailability.created_at.desc()).limit(limit).all()
        
        lines = []
        center_msg = f" for center '{visa_center}'" if visa_center else " across all centers"
        
        if active_slots:
            lines.append(f"Found {len(active_slots)} ACTIVE open slot window(s){center_msg}:")
            for s in active_slots:
                times = []
                if isinstance(s.slots_data, list):
                    times = [str(x) for x in s.slots_data[:4]]
                time_str = f" (Times: {', '.join(times)})" if times else ""
                found_age = (datetime.utcnow() - s.created_at).total_seconds() if s.created_at else None
                lines.append(f"- Center {s.visa_center} on {s.date}{time_str} - Found by {s.found_by or 'worker'} ({format_human_age(found_age)})")
        else:
            lines.append(f"No currently active appointment slots available{center_msg}.")
            
        # 2. Check historical discoveries in the last N days
        lookback_days = days if (days and days > 0) else 7
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        
        hist_query = sdb.query(SlotAvailability).filter(
            SlotAvailability.created_at >= cutoff
        )
        if visa_center and str(visa_center).strip():
            hist_query = hist_query.filter(SlotAvailability.visa_center.ilike(f"%{str(visa_center).strip()}%"))
            
        hist_slots = hist_query.order_by(SlotAvailability.created_at.desc()).limit(limit).all()
        active_ids = {s.id for s in active_slots}
        past_slots = [s for s in hist_slots if s.id not in active_ids]
        
        if past_slots:
            lines.append(f"\nHistorical Slot Discoveries in the last {lookback_days} days{center_msg}:")
            for s in past_slots:
                times = []
                if isinstance(s.slots_data, list):
                    times = [str(x) for x in s.slots_data[:4]]
                time_str = f" (Times: {', '.join(times)})" if times else ""
                age_val = (datetime.utcnow() - s.created_at).total_seconds() if s.created_at else None
                lines.append(f"- Center {s.visa_center} on {s.date}{time_str} - Discovered by {s.found_by or 'worker'} ({format_human_age(age_val)}, status: {s.status})")
        elif not active_slots:
            lines.append(f"No historical slots were discovered in the last {lookback_days} days{center_msg} either.")
            
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


# ---------------------------------------------------------------------------
# 3. Proxy Capabilities
# ---------------------------------------------------------------------------

def get_proxy_health(db: Optional[Session] = None) -> str:
    """Inspect proxy pool health, active connections, and cooldown states."""
    sdb = db or SessionLocal()
    try:
        proxies = sdb.query(Proxy).all()
        if not proxies:
            return "No proxies configured in the system."
            
        total = len(proxies)
        now = datetime.utcnow()
        cooldown = sum(1 for p in proxies if getattr(p, 'cooldown_until', None) and p.cooldown_until > now)
        active = sum(1 for p in proxies if (getattr(p, 'status', 'READY') or 'READY').upper() in ['READY', 'LEASED', 'ACTIVE'] and not (getattr(p, 'cooldown_until', None) and p.cooldown_until > now))
        failed = total - active
        
        lines = [
            f"Proxy Pool Status: {active}/{total} active ({cooldown} in cooldown, {failed} inactive).",
            "Rotation & TLS profiles are operating normally."
        ]
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


# ---------------------------------------------------------------------------
# 4. System & Leases Capabilities
# ---------------------------------------------------------------------------

def get_active_leases(limit: int = 15, db: Optional[Session] = None) -> str:
    """List currently active scraping and booking leases."""
    sdb = db or SessionLocal()
    try:
        leases = sdb.query(Lease).filter(
            Lease.status.in_(["Leased", "Running", "Pending"])
        ).order_by(Lease.created_at.desc()).limit(limit).all()
        
        if not leases:
            return "No active or pending worker leases."
            
        lines = [f"Active Leases ({len(leases)}):"]
        for l in leases:
            age = (datetime.utcnow() - l.created_at).total_seconds() if l.created_at else 0
            lines.append(f"- Lease #{l.id} [{l.status}] - Worker: {l.worker_id} - Age: {format_human_duration(age)}")
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


def get_portal_health_summary(db: Optional[Session] = None) -> str:
    """Comprehensive system health diagnostics, stale scraping checks, worker errors, and actionable recommendations."""
    sdb = db or SessionLocal()
    try:
        from datetime import timedelta
        now = datetime.utcnow()
        lines = ["=== TRAVELOS OPERATIONAL HEALTH REPORT ==="]
        recommendations = []
        
        # 1. Scraping Freshness & Last Check Inspection
        last_check_event = sdb.query(EventLog).filter(
            EventLog.event_type.in_(['SLOT_FOUND', 'NO_SLOTS_FOUND', 'LEASE_COMPLETED', 'LOGIN_SUCCESS'])
        ).order_by(EventLog.created_at.desc()).first()
        
        last_asm = sdb.query(Assignment).filter(
            Assignment.last_checked.isnot(None)
        ).order_by(Assignment.last_checked.desc()).first()
        
        check_times = [t for t in [last_check_event.created_at if last_check_event else None, last_asm.last_checked if last_asm else None] if t]
        last_check_time = max(check_times) if check_times else None
        
        if last_check_time:
            age_sec = int((datetime.utcnow() - last_check_time).total_seconds())
            if age_sec > 86400:
                age_str = f"{round(age_sec / 86400, 1)} day(s) ago"
            elif age_sec > 3600:
                age_str = f"{round(age_sec / 3600, 1)} hour(s) ago"
            elif age_sec > 60:
                age_str = f"{int(age_sec / 60)} minute(s) ago"
            else:
                age_str = f"{age_sec} second(s) ago"
                
            if age_sec > 900: # > 15 minutes
                lines.append(f"[SCRAPING PIPELINE] STALE - Last checked {age_str} (Expected: ~5 mins).")
                recommendations.append("Scraping has stalled. Check worker processes or click [Cleanup] to reconcile leases.")
            else:
                lines.append(f"[SCRAPING PIPELINE] HEALTHY - Last checked {age_str}.")
        else:
            lines.append("[SCRAPING PIPELINE] NEVER CHECKED - No slot check events recorded in database.")
            recommendations.append("No slot checks recorded. Verify scraping workers are running and accepting jobs.")

        # 2. Worker Fleet Status
        workers = sdb.query(WorkerNode).all()
        total_w = len(workers)
        online_w = sum(1 for w in workers if w.is_online)
        err_w = sum(1 for w in workers if w.status == "Error")
        lines.append(f"[WORKER FLEET] {online_w}/{total_w} online ({err_w} in error status).")
        if online_w == 0:
            recommendations.append("Zero scraping workers are currently online. Check worker host / Docker services.")

        # 3. Portal Accounts & Proxies
        accounts = sdb.query(PortalAccount).all()
        proxies = sdb.query(Proxy).all()
        acc_counts = {}
        for a in accounts:
            st = getattr(a, 'status', 'READY') or 'READY'
            acc_counts[st] = acc_counts.get(st, 0) + 1
            
        acc_str = ", ".join([f"{k}: {v}" for k, v in acc_counts.items()]) if acc_counts else "0 total"
        lines.append(f"[PORTAL ACCOUNTS] {len(accounts)} total ({acc_str})")
        ready_accs = acc_counts.get('READY', 0)
        active_prx = sum(1 for p in proxies if (getattr(p, 'status', 'READY') or 'READY').upper() in ['READY', 'LEASED', 'ACTIVE'] and not (getattr(p, 'cooldown_until', None) and p.cooldown_until > now))
        lines.append(f"[PROXIES] {active_prx}/{len(proxies)} active.")
        if active_prx == 0 and len(proxies) > 0:
            recommendations.append("All proxies are inactive or failing. Verify proxy configurations.")

        # 4. Recent Worker Error Logs (Last 24 hours)
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        recent_errors = sdb.query(EventLog).filter(
            EventLog.event_type.in_(['PROXY_TIMEOUT', 'LOGIN_FAILED', 'CLOUDFLARE_BLOCKED', 'ERROR', 'WORKER_ERROR', 'LEASE_TIMEOUT', 'ACCOUNT_LOCKED', 'CAPTCHA_BLOCKED']),
            EventLog.created_at >= cutoff_24h
        ).order_by(EventLog.created_at.desc()).limit(5).all()
        
        if recent_errors:
            lines.append(f"[RECENT WORKER ERRORS] ({len(recent_errors)} in last 24h):")
            for ev in recent_errors:
                msg = ""
                if ev.payload and isinstance(ev.payload, dict):
                    msg = ev.payload.get("message") or ev.payload.get("error") or str(ev.payload)[:60]
                lines.append(f" - [{ev.created_at.strftime('%H:%M')}] {ev.worker_id or 'worker'}: {ev.event_type} - {msg}")
                if "PROXY" in ev.event_type:
                    recommendations.append(f"Worker {ev.worker_id} hit proxy timeout. Inspect or rotate proxy pool.")
                elif "CLOUDFLARE" in ev.event_type:
                    recommendations.append("Cloudflare challenge encountered. Check TLS fingerprint / curl_cffi settings.")
        else:
            lines.append("[RECENT ERRORS] No critical worker errors recorded in the last 24 hours.")

        # 5. Push Notifications Health
        sub_count = sdb.query(PushSubscription).count()
        if sub_count == 0:
            lines.append("[PUSH NOTIFICATIONS] 0 devices subscribed in database.")
            recommendations.append("You have not enabled push notifications on this device. Click 'Enable Notifications' in the PWA sidebar.")
        else:
            lines.append(f"[PUSH NOTIFICATIONS] {sub_count} active device subscription(s) registered.")

        # 6. Actionable Guidance / Recommendations
        if recommendations:
            seen_recs = set()
            dedup_recs = []
            for r in recommendations:
                if r not in seen_recs:
                    seen_recs.add(r)
                    dedup_recs.append(r)
            lines.append("\n[ACTIONABLE RECOMMENDATIONS]")
            for i, rec in enumerate(dedup_recs, 1):
                lines.append(f" {i}. {rec}")
        else:
            lines.append("\n[SYSTEM STATUS] System is operating optimally with no action required.")

        return "\n".join(lines)
    finally:
        if not db: sdb.close()


def trigger_maintenance_cycle(db: Optional[Session] = None) -> str:
    """Reconcile orphaned resources and expired leases."""
    sdb = db or SessionLocal()
    try:
        from services.maintenance_service import MaintenanceService
        svc = MaintenanceService(sdb)
        if hasattr(svc, '_reconcile_orphan_resources'):
            svc._reconcile_orphan_resources()
        if hasattr(svc, 'cleanup_expired_leases'):
            svc.cleanup_expired_leases()
        return "Maintenance cycle executed: Orphaned accounts/proxies reconciled and expired leases cleaned."
    except Exception as e:
        return f"Maintenance error: {str(e)}"
    finally:
        if not db: sdb.close()


def unlease_resource(resource_type: str, resource_id: int, db: Optional[Session] = None) -> str:
    """Reset a stuck account or proxy to READY."""
    sdb = db or SessionLocal()
    try:
        rtype = resource_type.strip().lower()
        if rtype == "account":
            acc = sdb.query(PortalAccount).filter(PortalAccount.id == resource_id).first()
            if not acc: return f"Account {resource_id} not found."
            acc.status = "READY"
            acc.is_locked = False
            sdb.commit()
            return f"Account {acc.username} reset to READY."
        elif rtype == "proxy":
            prx = sdb.query(Proxy).filter(Proxy.id == resource_id).first()
            if not prx: return f"Proxy {resource_id} not found."
            prx.status = "READY"
            sdb.commit()
            return f"Proxy {prx.host}:{prx.port} reset to READY."
        elif rtype == "lease":
            l = sdb.query(Lease).filter(Lease.id == resource_id).first()
            if not l: return f"Lease {resource_id} not found."
            l.status = "Abandoned"
            sdb.commit()
            return f"Lease #{resource_id} marked as Abandoned."
        return f"Invalid resource type '{resource_type}'."
    except Exception as e:
        sdb.rollback()
        return f"Error unleasing: {str(e)}"
    finally:
        if not db: sdb.close()


# ---------------------------------------------------------------------------
# 5. Capability Registry & Intent-Filtered Tool Declarations
# ---------------------------------------------------------------------------

CAPABILITY_DEFINITIONS = {
    "worker.get_status": {
        "fn": get_worker_details,
        "description": "Inspect detailed state, heartbeat, and current assignment of a specific worker.",
        "params": '{"worker_id": "string"}',
        "tags": ["worker", "workers", "failing", "stuck", "waiting", "node", "status"]
    },
    "worker.get_recent_logs": {
        "fn": get_worker_logs,
        "description": "Retrieve recent log events and error traces for a worker.",
        "params": '{"worker_id": "string", "limit": 5}',
        "tags": ["worker", "log", "logs", "error", "failing", "crash", "trace"]
    },
    "worker.list_all": {
        "fn": get_workers,
        "description": "List all registered scraping and booking workers.",
        "params": '{}',
        "tags": ["worker", "workers", "fleet", "nodes", "online"]
    },
    "slots.get_available": {
        "fn": get_available_slots,
        "description": "Check currently available visa appointment slots in the system.",
        "params": '{"visa_center": "string (optional)", "limit": 10}',
        "tags": ["slot", "slots", "appointment", "availability", "dates", "open"]
    },
    "proxy.get_health": {
        "fn": get_proxy_health,
        "description": "Check proxy pool health, active counts, and cooldowns.",
        "params": '{}',
        "tags": ["proxy", "proxies", "ip", "rotation", "health"]
    },
    "system.get_health": {
        "fn": get_portal_health_summary,
        "description": "Summary of portal accounts, health, and proxies.",
        "params": '{}',
        "tags": ["system", "health", "accounts", "portal", "status"]
    },
    "system.get_active_leases": {
        "fn": get_active_leases,
        "description": "List active scraping and booking worker leases.",
        "params": '{"limit": 15}',
        "tags": ["lease", "leases", "active", "running"]
    },
    "system.maintenance": {
        "fn": trigger_maintenance_cycle,
        "description": "Reconcile orphaned accounts/proxies and clean expired leases.",
        "params": '{}',
        "tags": ["maintenance", "cleanup", "reconcile"]
    }
}


def filter_relevant_tools(user_query: str) -> List[Dict[str, Any]]:
    """Filters capabilities relevant to the query to avoid overwhelming the 2.7B model."""
    q = user_query.lower()
    selected = []
    
    for name, meta in CAPABILITY_DEFINITIONS.items():
        if any(tag in q for tag in meta["tags"]):
            selected.append({"name": name, "description": meta["description"], "params": meta["params"]})
            
    # Default set if no specific keyword matched
    if not selected:
        for name in ["worker.list_all", "slots.get_available", "proxy.get_health", "system.get_health"]:
            meta = CAPABILITY_DEFINITIONS[name]
            selected.append({"name": name, "description": meta["description"], "params": meta["params"]})
            
    return selected[:4]


def format_tool_declarations(tools: List[Dict[str, Any]]) -> str:
    """Formats selected tool definitions into concise text signatures."""
    lines = ["Available Operational Tools:"]
    for t in tools:
        lines.append(f"- {t['name']}({t['params']}): {t['description']}")
    return "\n".join(lines)


def execute_capability(tool_name: str, args: Dict[str, Any], db: Optional[Session] = None) -> str:
    """Safely executes a registered capability with validated arguments."""
    t_name = tool_name.strip()
    
    canonical_map = {
        "get_portal_health_summary": "system.get_health",
        "portal_health_summary": "system.get_health",
        "system_health": "system.get_health",
        "get_workers": "worker.list_all",
        "get_worker_details": "worker.get_status",
        "get_worker_status": "worker.get_status",
        "get_worker_logs": "worker.get_recent_logs",
        "get_available_slots": "slots.get_available",
        "get_proxy_health": "proxy.get_health",
        "proxy_health": "proxy.get_health",
        "get_active_leases": "system.get_active_leases",
        "active_leases": "system.get_active_leases",
        "trigger_maintenance_cycle": "system.maintenance",
        "maintenance": "system.maintenance",
        "cleanup": "system.maintenance",
        "unlease_resource": "system.unlease"
    }
    
    mapped_name = canonical_map.get(t_name, t_name)
    meta = CAPABILITY_DEFINITIONS.get(mapped_name)
    
    if meta:
        fn = meta["fn"]
    else:
        direct_fns = {
            "get_portal_health_summary": get_portal_health_summary,
            "get_workers": get_workers,
            "get_worker_details": get_worker_details,
            "get_worker_status": get_worker_details,
            "get_worker_logs": get_worker_logs,
            "get_available_slots": get_available_slots,
            "get_proxy_health": get_proxy_health,
            "get_active_leases": get_active_leases,
            "trigger_maintenance_cycle": trigger_maintenance_cycle,
            "unlease_resource": unlease_resource
        }
        fn = direct_fns.get(t_name)
        if not fn:
            return f"Unknown tool '{tool_name}'."
        
    try:
        import inspect
        sig = inspect.signature(fn)
        call_args = {}
        for p_name in sig.parameters:
            if p_name == "db":
                call_args["db"] = db
            elif p_name in args:
                call_args[p_name] = args[p_name]
            elif p_name == "worker_id":
                found = None
                for k, v in args.items():
                    if "worker" in str(k).lower():
                        found = str(k)
                        break
                    elif "worker" in str(v).lower():
                        found = str(v)
                        break
                if found:
                    call_args["worker_id"] = found
            elif p_name == "visa_center":
                for k, v in args.items():
                    if any(c in str(k).lower() for c in ["center", "vac"]):
                        call_args["visa_center"] = str(v)
                        break
                
        return str(fn(**call_args))
    except Exception as e:
        return f"Execution error in {tool_name}: {str(e)}"
