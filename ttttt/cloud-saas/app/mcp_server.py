try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except Exception:
        class FastMCP:
            def __init__(self, name="KESaaSAdmin"):
                self.name = name
                self._tools = {}
            def tool(self, *args, **kwargs):
                def decorator(fn):
                    self._tools[fn.__name__] = fn
                    return fn
                return decorator
            async def list_tools(self):
                from types import SimpleNamespace
                return [SimpleNamespace(name=k, description=v.__doc__ or "", inputSchema={}) for k, v in self._tools.items()]
            async def call_tool(self, name, args):
                if name in self._tools:
                    fn = self._tools[name]
                    import inspect
                    sig = inspect.signature(fn)
                    cargs = {k: v for k, v in args.items() if k in sig.parameters}
                    return [fn(**cargs)]
                return [f"Tool {name} not found"]

from sqlalchemy.orm import Session
from datetime import datetime
import os
import services.travelos_capabilities as caps

mcp = FastMCP("KESaaSAdmin")

@mcp.tool()
def get_workers() -> str:
    """Get a list of all registered workers and their status."""
    return caps.get_workers()

@mcp.tool()
def get_worker_details(worker_id: str) -> str:
    """Inspect detailed status, active lease, and assignment context for a specific worker."""
    return caps.get_worker_details(worker_id=worker_id)

@mcp.tool()
def get_worker_status(worker_id: str) -> str:
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
