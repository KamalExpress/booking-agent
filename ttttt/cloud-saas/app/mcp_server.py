from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
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
        return "\n".join([f"ID: {w.worker_id}, Host: {w.hostname}, Can Scrape: {w.can_scrape}, Can Book: {w.can_book}" for w in workers])
    finally:
        db.close()

@mcp.tool()
def create_mock_worker(worker_id: str = "mock-worker-1", can_scrape: bool = True, can_book: bool = True) -> str:
    """Register a mock worker to the system."""
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
            can_book=can_book
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

