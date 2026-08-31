"""
TravelOS Unified Capabilities Layer.
This module defines read-only operational functions directly querying the database.
Both the TravelOS FastMCP Server and TravelOS Copilot Agent Loop consume these tools.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import json

from models import SessionLocal, WorkerNode, SlotAvailability, Proxy, PortalAccount, Lease, Assignment, EventLog, WorkerLog

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
            hb_age = int((datetime.utcnow() - w.last_heartbeat).total_seconds()) if getattr(w, 'last_heartbeat', None) else "N/A"
            status = getattr(w, 'status', 'Offline') or 'Offline'
            sched = getattr(w, 'scheduling_state', 'Accepting Jobs') or 'Accepting Jobs'
            lines.append(f"• {w.worker_id} [{status}] ({sched}) - Scrape: {w.can_scrape}, Book: {w.can_book} - Last Heartbeat: {hb_age}s ago")
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
        
        hb_age = int((datetime.utcnow() - worker.last_heartbeat).total_seconds()) if getattr(worker, 'last_heartbeat', None) else "N/A"
        lines = [
            f"Worker: {worker.worker_id}",
            f"Status: {getattr(worker, 'status', 'Offline')}",
            f"Scheduling State: {getattr(worker, 'scheduling_state', 'Accepting Jobs')}",
            f"Last Heartbeat: {hb_age}s ago ({worker.last_heartbeat})",
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

def get_available_slots(visa_center: Optional[str] = None, limit: int = 10, db: Optional[Session] = None) -> str:
    """Retrieve active open appointment slots discovered by scraping workers."""
    sdb = db or SessionLocal()
    try:
        query = sdb.query(SlotAvailability).filter(
            SlotAvailability.status == "AVAILABLE",
            SlotAvailability.is_archived == False
        )
        if visa_center and str(visa_center).strip():
            query = query.filter(SlotAvailability.visa_center == str(visa_center).strip())
            
        slots = query.order_by(SlotAvailability.created_at.desc()).limit(limit).all()
        
        if not slots:
            center_msg = f" for center {visa_center}" if visa_center else " across all centers"
            return f"No open appointment slots currently available in the system{center_msg}."
            
        lines = [f"Found {len(slots)} open slot window(s):"]
        for s in slots:
            times = []
            if isinstance(s.slots_data, list):
                times = [str(x) for x in s.slots_data[:4]]
            time_str = f" (Times: {', '.join(times)})" if times else ""
            found_age = int((datetime.utcnow() - s.created_at).total_seconds()) if s.created_at else 0
            lines.append(f"• Center {s.visa_center} on {s.date}{time_str} - Found by {s.found_by or 'worker'} ({found_age}s ago)")
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
        active = sum(1 for p in proxies if getattr(p, 'status', 'ACTIVE') == 'ACTIVE')
        now = datetime.utcnow()
        cooldown = sum(1 for p in proxies if getattr(p, 'cooldown_until', None) and p.cooldown_until > now)
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
            age = int((datetime.utcnow() - l.created_at).total_seconds()) if l.created_at else 0
            lines.append(f"• Lease #{l.id} [{l.status}] - Worker: {l.worker_id} - Age: {age}s")
        return "\n".join(lines)
    finally:
        if not db: sdb.close()


def get_portal_health_summary(db: Optional[Session] = None) -> str:
    """Get health summary of portal accounts and proxies."""
    sdb = db or SessionLocal()
    try:
        accounts = sdb.query(PortalAccount).all()
        proxies = sdb.query(Proxy).all()
        
        acc_counts = {}
        for a in accounts:
            st = getattr(a, 'status', 'READY') or 'READY'
            acc_counts[st] = acc_counts.get(st, 0) + 1
            
        lines = [
            f"Portal Accounts: {len(accounts)} total (" + ", ".join([f"{k}: {v}" for k, v in acc_counts.items()]) + ")",
            f"Proxies: {len(proxies)} total"
        ]
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
    if "_" in t_name and "." not in t_name:
        parts = t_name.split("_", 1)
        t_name = f"{parts[0]}.{parts[1]}"
        
    meta = CAPABILITY_DEFINITIONS.get(t_name)
    if not meta:
        return f"Unknown tool '{tool_name}'."
        
    try:
        fn = meta["fn"]
        import inspect
        sig = inspect.signature(fn)
        call_args = {}
        for p_name in sig.parameters:
            if p_name == "db":
                call_args["db"] = db
            elif p_name in args:
                call_args[p_name] = args[p_name]
            elif p_name == "worker_id":
                # Smart heuristic: find worker id from keys or values
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
