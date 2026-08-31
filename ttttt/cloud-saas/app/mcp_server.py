from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from datetime import datetime
import os

mcp = FastMCP("KESaaSAdmin")

@mcp.tool()
def get_workers() -> str:
    """Get a list of all registered workers and their status."""
    from models import SessionLocal, WorkerNode
    db: Session = SessionLocal()
    try:
        workers = db.query(WorkerNode).all()
        if not workers:
            return "No workers found."
        out = []
        for w in workers:
            hb_age = int((datetime.utcnow() - w.last_heartbeat).total_seconds()) if getattr(w, 'last_heartbeat', None) else "N/A"
            out.append(f"ID: {w.worker_id} | Host: {w.hostname} | Status: {getattr(w, 'status', 'READY')} | Scrape: {w.can_scrape} | Book: {w.can_book} | HB: {hb_age}s ago")
        return "\n".join(out)
    except Exception as e:
        return f"Error fetching workers: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def create_mock_worker(worker_id: str = "mock-worker-1", can_scrape: bool = True, can_book: bool = True) -> str:
    """Register a mock worker to the system for scheduler testing."""
    from models import SessionLocal, WorkerNode
    db: Session = SessionLocal()
    try:
        worker = db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
        if worker:
            return f"Worker {worker_id} already exists."
            
        worker = WorkerNode(
            worker_id=worker_id,
            hostname="mock-host",
            machine_id="mock-machine",
            os="linux",
            architecture="x64",
            ram="16GB",
            version="1.0.0",
            can_scrape=can_scrape,
            can_book=can_book,
            last_heartbeat=datetime.utcnow()
        )
        db.add(worker)
        db.commit()
        return f"Mock worker {worker_id} created successfully."
    except Exception as e:
        db.rollback()
        return f"Failed: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_active_leases(limit: int = 20) -> str:
    """List all currently active or pending worker leases with associated accounts and proxies."""
    from models import SessionLocal, Lease, PortalAccount, Proxy, Assignment
    db: Session = SessionLocal()
    try:
        leases = db.query(Lease).filter(Lease.status.in_(["Leased", "Running", "Pending"])).order_by(Lease.created_at.desc()).limit(limit).all()
        if not leases:
            return "No active or pending leases found."
        out = []
        for l in leases:
            acc = db.query(PortalAccount).filter(PortalAccount.id == l.portal_account_id).first() if l.portal_account_id else None
            prx = db.query(Proxy).filter(Proxy.id == l.proxy_id).first() if l.proxy_id else None
            asg = db.query(Assignment).filter(Assignment.id == l.assignment_id).first() if l.assignment_id else None
            
            acc_label = acc.username if acc else "None"
            prx_label = f"{prx.host}:{prx.port}" if prx else "None"
            vac_label = asg.visa_center if asg else "None"
            
            age_seconds = int((datetime.utcnow() - l.created_at).total_seconds()) if l.created_at else 0
            out.append(f"Lease #{l.id} | Worker: {l.worker_id} | Status: {l.status} | VAC: {vac_label} | Account: {acc_label} | Proxy: {prx_label} | Age: {age_seconds}s")
        return "\n".join(out)
    except Exception as e:
        return f"Error fetching active leases: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def unlease_resource(resource_type: str, resource_id: int) -> str:
    """Forcefully unlock a stuck resource (resource_type: 'account', 'proxy', or 'lease') back to READY."""
    from models import SessionLocal, PortalAccount, Proxy, Lease
    db: Session = SessionLocal()
    try:
        rtype = resource_type.strip().lower()
        if rtype == "account":
            acc = db.query(PortalAccount).filter(PortalAccount.id == resource_id).first()
            if not acc:
                return f"PortalAccount ID {resource_id} not found."
            acc.status = "READY"
            acc.is_locked = False
            db.commit()
            return f"PortalAccount {acc.username} (ID {resource_id}) unleased and reset to READY."
        elif rtype == "proxy":
            prx = db.query(Proxy).filter(Proxy.id == resource_id).first()
            if not prx:
                return f"Proxy ID {resource_id} not found."
            prx.status = "READY"
            db.commit()
            return f"Proxy {prx.host}:{prx.port} (ID {resource_id}) unleased and reset to READY."
        elif rtype == "lease":
            l = db.query(Lease).filter(Lease.id == resource_id).first()
            if not l:
                return f"Lease ID {resource_id} not found."
            l.status = "Abandoned"
            if l.portal_account_id:
                acc = db.query(PortalAccount).filter(PortalAccount.id == l.portal_account_id).first()
                if acc:
                    acc.status = "READY"
                    acc.is_locked = False
            if l.proxy_id:
                prx = db.query(Proxy).filter(Proxy.id == l.proxy_id).first()
                if prx:
                    prx.status = "READY"
            db.commit()
            return f"Lease #{resource_id} marked as Abandoned and associated resources freed to READY."
        else:
            return f"Invalid resource_type '{resource_type}'. Use 'account', 'proxy', or 'lease'."
    except Exception as e:
        db.rollback()
        return f"Error unleasing resource: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_portal_health_summary() -> str:
    """Get health scores, statuses, and cooldowns for all accounts and proxies with schema-safe lookups."""
    from models import SessionLocal, PortalAccount, Proxy
    db: Session = SessionLocal()
    try:
        accounts = db.query(PortalAccount).all()
        proxies = db.query(Proxy).all()
        
        acc_counts = {}
        for a in accounts:
            st = getattr(a, 'status', 'UNKNOWN') or 'UNKNOWN'
            acc_counts[st] = acc_counts.get(st, 0) + 1
            
        prx_counts = {}
        for p in proxies:
            st = getattr(p, 'status', 'UNKNOWN') or 'UNKNOWN'
            prx_counts[st] = prx_counts.get(st, 0) + 1
            
        lines = ["=== Portal Accounts Summary ==="]
        lines.append(f"Total: {len(accounts)} | " + " | ".join([f"{k}: {v}" for k, v in acc_counts.items()]))
        
        cooldown_accounts = [a for a in accounts if getattr(a, 'cooldown_until', None) and a.cooldown_until > datetime.utcnow()]
        if cooldown_accounts:
            lines.append("Accounts in Cooldown:")
            for a in cooldown_accounts:
                remaining = int((a.cooldown_until - datetime.utcnow()).total_seconds())
                lines.append(f"  - {a.username} (ID {a.id}): cooldown for {remaining}s remaining")
        
        lines.append("\n=== Proxies Summary ===")
        lines.append(f"Total: {len(proxies)} | " + " | ".join([f"{k}: {v}" for k, v in prx_counts.items()]))
        
        cooldown_proxies = [p for p in proxies if getattr(p, 'cooldown_until', None) and p.cooldown_until > datetime.utcnow()]
        if cooldown_proxies:
            lines.append("Proxies in Cooldown:")
            for p in cooldown_proxies:
                remaining = int((p.cooldown_until - datetime.utcnow()).total_seconds())
                lines.append(f"  - {p.host}:{p.port} (ID {p.id}): cooldown for {remaining}s remaining")
                
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching portal health: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def trigger_maintenance_cycle() -> str:
    """Trigger the orphan resource reconciliation and lease cleanup routine immediately."""
    from models import SessionLocal
    from services.maintenance_service import MaintenanceService
    db: Session = SessionLocal()
    try:
        service = MaintenanceService(db)
        if hasattr(service, '_reconcile_orphan_resources'):
            service._reconcile_orphan_resources()
        if hasattr(service, 'cleanup_expired_leases'):
            service.cleanup_expired_leases()
        return "Maintenance cycle executed successfully. Orphaned accounts/proxies reconciled and expired leases cleaned up."
    except Exception as e:
        return f"Error running maintenance cycle: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def inject_test_booking_task(visa_center: str = "1", target_date: str = "2026-09-15", applicant_name: str = "Test Applicant") -> str:
    """Inject a test booking task to dry-run booker workers on Staging."""
    from models import SessionLocal, BookingTask
    import uuid
    db: Session = SessionLocal()
    try:
        task = BookingTask(
            visa_center=visa_center,
            target_date=target_date,
            target_time="09:00",
            active_status="PENDING",
            applicant_details={
                "first_name": applicant_name.split()[0],
                "last_name": applicant_name.split()[-1] if " " in applicant_name else "Tester",
                "passport_number": f"P{uuid.uuid4().hex[:7].upper()}",
                "is_test_dry_run": True
            }
        )
        db.add(task)
        db.commit()
        return f"Test BookingTask #{task.id} created successfully for VAC {visa_center} on {target_date} (Status: PENDING)."
    except Exception as e:
        db.rollback()
        return f"Failed to inject test booking task: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def inject_otp_code(task_id: int, otp_code: str) -> str:
    """Inject an OTP / 2FA verification code into an active booking task."""
    from models import SessionLocal, BookingTask
    db: Session = SessionLocal()
    try:
        task = db.query(BookingTask).filter(BookingTask.id == task_id).first()
        if not task:
            return f"BookingTask #{task_id} not found."
        
        details = task.applicant_details or {}
        if isinstance(details, dict):
            details["otp_code"] = otp_code
            task.applicant_details = details
        
        if hasattr(task, 'confirmation_payload'):
            payload = getattr(task, 'confirmation_payload') or {}
            if isinstance(payload, dict):
                payload["otp_code"] = otp_code
                setattr(task, 'confirmation_payload', payload)
                
        db.commit()
        return f"OTP code '{otp_code}' successfully injected into BookingTask #{task_id}."
    except Exception as e:
        db.rollback()
        return f"Failed to inject OTP code: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def update_system_setting(key: str, value: str) -> str:
    """Update or create a system configuration setting in the database."""
    from models import SessionLocal, SystemSetting
    db: Session = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            old_val = setting.value
            setting.value = value
            db.commit()
            return f"SystemSetting '{key}' updated: '{old_val}' -> '{value}'."
        else:
            new_setting = SystemSetting(key=key, value=value)
            db.add(new_setting)
            db.commit()
            return f"SystemSetting '{key}' created with value '{value}'."
    except Exception as e:
        db.rollback()
        return f"Failed to update setting: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def fetch_agent_monitor_logs() -> str:
    """Fetch the latest terminal logs and DB event logs for all workers."""
    from models import SessionLocal, EventLog
    db: Session = SessionLocal()
    try:
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "worker_logs")
        terminal_logs = {}
        if os.path.exists(logs_dir):
            for f in os.listdir(logs_dir):
                if f.endswith(".log"):
                    filepath = os.path.join(logs_dir, f)
                    with open(filepath, "r", encoding="utf-8", errors="replace") as lf:
                        lines = lf.readlines()
                        terminal_logs[f] = "".join(lines[-150:])
        
        recent_db_logs = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(100).all()
        db_logs_out = []
        for log in recent_db_logs:
            db_logs_out.append(f"[{log.created_at}] {log.worker_id}: {log.event_type} - {log.payload}")
            
        res = "--- Terminal Logs ---\n"
        for k, v in terminal_logs.items():
            res += f"File: {k}\n{v}\n"
        res += "\n--- DB Logs ---\n"
        res += "\n".join(db_logs_out)
        return res
    finally:
        db.close()

