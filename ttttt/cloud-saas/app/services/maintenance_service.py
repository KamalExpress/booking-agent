from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends

from models import Lease, LeaseArchive, WorkerNode, EventLog, get_db

class MaintenanceService:
    def __init__(self, db: Session):
        self.db = db
        
    def run_cleanup_cycle(self):
        """
        Runs all maintenance cleanup tasks defensively.
        Should be invoked by high-traffic endpoints periodically (or every time, since it's cheap if fast).
        """
        self._worker_cleanup()
        self._lease_cleanup()
        self._notification_cleanup()
        
    def _worker_cleanup(self):
        # 1. Find workers offline
        # The WORKER_TIMEOUT_SECONDS is 90
        cutoff = datetime.utcnow() - timedelta(seconds=90)
        
        # We need to find workers that are Online but haven't sent a heartbeat since cutoff
        dead_workers = self.db.query(WorkerNode).filter(
            WorkerNode.status == "Online",
            WorkerNode.last_heartbeat < cutoff
        ).all()
        
        for w in dead_workers:
            w.status = "Offline"
            # Emit EventLog
            log = EventLog(
                source="maintenance",
                worker_id=w.worker_id,
                severity="warning",
                event_type="WORKER_OFFLINE",
                payload={"reason": "heartbeat_timeout"}
            )
            self.db.add(log)
            
        if dead_workers:
            self.db.commit()

    def _lease_cleanup(self):
        # Move Completed, Expired, Cancelled, Failed, Abandoned leases older than 24h to LeaseArchive
        cutoff = datetime.utcnow() - timedelta(hours=24)
        old_leases = self.db.query(Lease).filter(
            Lease.status.in_(["Completed", "Expired", "Cancelled", "Failed", "Abandoned"]),
            Lease.created_at < cutoff
        ).all()
        
        for lease in old_leases:
            archive = LeaseArchive(
                assignment_id=lease.assignment_id,
                worker_id=lease.worker_id,
                expires_at=lease.expires_at,
                last_heartbeat=lease.last_heartbeat,
                status=lease.status,
                created_at=lease.created_at,
                archived_at=datetime.utcnow()
            )
            self.db.add(archive)
            self.db.delete(lease)
            
        if old_leases:
            self.db.commit()

    def _notification_cleanup(self):
        # Delete EventLogs older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        self.db.query(EventLog).filter(EventLog.created_at < cutoff).delete(synchronize_session=False)
        self.db.commit()

def get_maintenance_service(db: Session = Depends(get_db)) -> MaintenanceService:
    return MaintenanceService(db)
