from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends

from models import Lease, Assignment, PortalAccount, WorkerNode, EventLog, get_db

class LeaseService:
    def __init__(self, db: Session):
        self.db = db

    def expire_stale_leases(self):
        now = datetime.utcnow()
        expired_leases = self.db.query(Lease).filter(
            Lease.expires_at < now,
            Lease.status.in_(["Leased", "Running"])
        ).all()
        for lease in expired_leases:
            lease.status = "Expired"
            assignment = self.db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
            if assignment:
                assignment.status = "Active"
                
            log = EventLog(
                source="lease_service",
                worker_id=lease.worker_id,
                assignment_id=lease.assignment_id,
                severity="warning",
                event_type="LEASE_EXPIRED",
                payload={"reason": "timeout"}
            )
            self.db.add(log)
            
        if expired_leases:
            self.db.commit()

    def get_existing_lease_for_worker(self, worker: WorkerNode) -> Optional[Dict[str, Any]]:
        existing_lease = self.db.query(Lease).filter(
            Lease.worker_id == worker.worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).first()
        
        if existing_lease:
            best_assignment = self.db.query(Assignment).filter(Assignment.id == existing_lease.assignment_id).first()
            if best_assignment:
                acc = self.db.query(PortalAccount).filter(PortalAccount.id == best_assignment.scraper_account_id).first()
                return self._build_lease_response(existing_lease, best_assignment, acc)
        return None

    def get_next_lease(self, worker: WorkerNode) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow()
        
        # 1. Find all active, unleased assignments
        assignments = self.db.query(Assignment).filter(Assignment.status == "Active").all()
        
        valid_assignments = []
        for asm in assignments:
            if not asm.last_checked or (now - asm.last_checked).total_seconds() >= asm.polling_interval:
                valid_assignments.append(asm)
                
        if not valid_assignments:
            return None
            
        # 2. Score assignments for this worker
        best_score = -9999
        best_assignment = None
        
        for asm in valid_assignments:
            # Check required labels
            if asm.required_labels:
                missing_or_mismatch = False
                for k, v in asm.required_labels.items():
                    if worker.labels.get(k) != v:
                        missing_or_mismatch = True
                        break
                if missing_or_mismatch:
                    continue
                    
            score = asm.priority * 10
            
            # Check PortalAccount preferred worker
            acc = self.db.query(PortalAccount).filter(PortalAccount.id == asm.scraper_account_id).first()
            if acc and acc.preferred_worker_id == worker.worker_id:
                score += 100
                
            if score > best_score:
                best_score = score
                best_assignment = asm
                
        if not best_assignment:
            return None
            
        # 3. Create Lease
        lease = Lease(
            assignment_id=best_assignment.id,
            worker_id=worker.worker_id,
            expires_at=datetime.utcnow() + timedelta(minutes=2),
            status="Leased",
            last_heartbeat=datetime.utcnow()
        )
        self.db.add(lease)
        best_assignment.status = "Leased"
        
        log = EventLog(
            source="lease_service",
            worker_id=worker.worker_id,
            assignment_id=best_assignment.id,
            severity="info",
            event_type="LEASE_CREATED",
            payload={"priority": best_assignment.priority}
        )
        self.db.add(log)
        
        self.db.commit()
        self.db.refresh(lease)
        
        # 4. Return Lease object
        acc = self.db.query(PortalAccount).filter(PortalAccount.id == best_assignment.scraper_account_id).first()
        return self._build_lease_response(lease, best_assignment, acc)

    def _build_lease_response(self, lease: Lease, assignment: Assignment, acc: Optional[PortalAccount]) -> Dict[str, Any]:
        return {
            "lease_id": lease.id,
            "assignment_context": {
                "id": assignment.id,
                "visa_center": assignment.visa_center,
                "date_from": assignment.date_from,
                "date_to": assignment.date_to
            },
            "scraper_account": {
                "id": acc.id,
                "username": acc.username,
                "password": acc.password,
                "proxy_string": acc.proxy_string,
                "proxy_mode": acc.proxy_mode
            } if acc else {},
            "expiry": lease.expires_at.isoformat(),
            "heartbeat_interval": WorkerNode.HEARTBEAT_INTERVAL_SECONDS
        }

    def extend_worker_leases(self, worker_id: str) -> int:
        active_leases = self.db.query(Lease).filter(
            Lease.worker_id == worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).all()
        for lease in active_leases:
            lease.last_heartbeat = datetime.utcnow()
            lease.expires_at = datetime.utcnow() + timedelta(minutes=2)
        if active_leases:
            self.db.commit()
        return len(active_leases)

    def complete_lease(self, worker_id: str, assignment_id: int):
        lease = self.db.query(Lease).filter(
            Lease.assignment_id == assignment_id, 
            Lease.worker_id == worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).first()
        if lease:
            lease.status = "Completed"
            log = EventLog(
                source="lease_service",
                worker_id=worker_id,
                assignment_id=assignment_id,
                severity="info",
                event_type="LEASE_COMPLETED",
                payload={}
            )
            self.db.add(log)
            
        assignment = self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if assignment:
            assignment.status = "Active"
            assignment.last_checked = datetime.utcnow()
            
        self.db.commit()

    def cancel_active_leases(self, assignment_ids: List[int]):
        leases = self.db.query(Lease).filter(
            Lease.assignment_id.in_(assignment_ids),
            Lease.status.in_(["Leased", "Running"])
        ).all()
        for lease in leases:
            lease.status = "Cancelled"
            log = EventLog(
                source="lease_service",
                worker_id=lease.worker_id,
                assignment_id=lease.assignment_id,
                severity="info",
                event_type="LEASE_CANCELLED",
                payload={"reason": "slot_found"}
            )
            self.db.add(log)
        if leases:
            self.db.commit()

def get_lease_service(db: Session = Depends(get_db)) -> LeaseService:
    return LeaseService(db)
