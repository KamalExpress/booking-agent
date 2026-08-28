from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends

try:
    from models import Lease, LeaseArchive, WorkerNode, EventLog, PortalAccount, Proxy, Assignment, get_db
except ImportError:
    from app.models import Lease, LeaseArchive, WorkerNode, EventLog, PortalAccount, Proxy, Assignment, get_db

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
        self._reconcile_orphan_resources()
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
        
        if dead_workers:
            from services.lease_service import LeaseService
            lease_svc = LeaseService(self.db)
            
            for w in dead_workers:
                w.status = "Offline"
                w.current_concurrency = 0
                
                # Abandon any active leases for this worker
                lease_svc.abandon_worker_leases(w.worker_id)
                
                # Emit EventLog
                log = EventLog(
                    source="maintenance",
                    worker_id=w.worker_id,
                    severity="warning",
                    event_type="WORKER_OFFLINE",
                    payload={"reason": "heartbeat_timeout"}
                )
                self.db.add(log)
                
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

    def _reconcile_orphan_resources(self):
        # 1. Reconcile Portal Accounts that are LEASED but have no active lease
        active_acc_query = self.db.query(Lease.portal_account_id).filter(
            Lease.status.in_(["Leased", "Running"]),
            Lease.portal_account_id.isnot(None)
        ).all()
        active_acc_ids = {a[0] for a in active_acc_query if a[0]}
        
        orphan_accounts = self.db.query(PortalAccount).filter(
            PortalAccount.status == "LEASED"
        ).all()
        for acc in orphan_accounts:
            if acc.id not in active_acc_ids:
                acc.status = "READY"
                
        # 2. Reconcile Proxies that are LEASED but have no active lease
        active_proxy_query = self.db.query(Lease.proxy_id).filter(
            Lease.status.in_(["Leased", "Running"]),
            Lease.proxy_id.isnot(None)
        ).all()
        active_proxy_ids = {p[0] for p in active_proxy_query if p[0]}
        
        orphan_proxies = self.db.query(Proxy).filter(
            Proxy.status == "LEASED"
        ).all()
        for prx in orphan_proxies:
            if prx.id not in active_proxy_ids:
                prx.status = "READY"
                
        # 3. Reconcile Assignments that are Leased but have no active lease
        active_asm_query = self.db.query(Lease.assignment_id).filter(
            Lease.status.in_(["Leased", "Running"]),
            Lease.assignment_id.isnot(None)
        ).all()
        active_asm_ids = {m[0] for m in active_asm_query if m[0]}
        
        orphan_assignments = self.db.query(Assignment).filter(
            Assignment.status == "Leased"
        ).all()
        for asm in orphan_assignments:
            if asm.id not in active_asm_ids:
                asm.status = "Active"
                
        self.db.commit()

    def _notification_cleanup(self):
        # Delete EventLogs older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        self.db.query(EventLog).filter(EventLog.created_at < cutoff).delete(synchronize_session=False)
        self.db.commit()

def get_maintenance_service(db: Session = Depends(get_db)) -> MaintenanceService:
    return MaintenanceService(db)
