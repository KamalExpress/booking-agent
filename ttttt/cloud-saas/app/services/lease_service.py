from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends

from models import Lease, Assignment, PortalAccount, Proxy, WorkerNode, BookingTask, EventLog, get_db

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
            
            # Reset PortalAccount status
            if lease.portal_account_id:
                account = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
                if account and account.status == "LEASED":
                    account.status = "READY"
            
            # Reset Proxy status
            if lease.proxy_id:
                proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first()
                if proxy and proxy.status == "LEASED":
                    proxy.status = "READY"
                    
            # Decrement worker concurrency
            worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == lease.worker_id).first()
            if worker and worker.current_concurrency > 0:
                worker.current_concurrency -= 1
                
            # Handle assignment resetting if scraping lease
            if lease.assignment_id:
                assignment = self.db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
                if assignment:
                    assignment.status = "Active"
                    
            # Handle booking task resetting if booking lease
            if lease.booking_task_id:
                task = self.db.query(BookingTask).filter(BookingTask.id == lease.booking_task_id).first()
                if task and task.status == "CLAIMED":
                    task.status = "PENDING"
                
            log = EventLog(
                source="lease_service",
                worker_id=lease.worker_id,
                assignment_id=lease.assignment_id,
                severity="warning",
                event_type="LEASE_EXPIRED",
                payload={"reason": "timeout", "booking_task_id": lease.booking_task_id} if lease.booking_task_id else {"reason": "timeout"}
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
                acc = self.db.query(PortalAccount).filter(PortalAccount.id == existing_lease.portal_account_id).first()
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
            
            # Preferred worker logic removed (handled by SchedulerService)
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
        acc = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
        return self._build_lease_response(lease, best_assignment, acc)

    def _build_lease_response(self, lease: Lease, assignment: Assignment, acc: Optional[PortalAccount]) -> Dict[str, Any]:
        proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first() if lease.proxy_id else None
        proxy_string = proxy.proxy_string if proxy else None
        
        return {
            "lease_id": lease.id,
            "assignment_context": {
                "id": assignment.id,
                "visa_center": assignment.visa_center,
                "date_from": assignment.date_from,
                "date_to": assignment.date_to
            },
            "scraper_account": {
                "id": acc.id if acc else 0,
                "username": acc.username if acc else "",
                "password": acc.password if acc else "",
                "proxy_string": proxy_string,
                "proxy_mode": "POOL"
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
            Lease.worker_id == worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).filter(
            (Lease.assignment_id == assignment_id) | (Lease.booking_task_id == assignment_id)
        ).first()
        
        if lease:
            lease.status = "Completed"
            
            # Reset PortalAccount status
            if lease.portal_account_id:
                account = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
                if account and account.status == "LEASED":
                    account.status = "READY"
            
            # Reset Proxy status
            if lease.proxy_id:
                proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first()
                if proxy and proxy.status == "LEASED":
                    proxy.status = "READY"
                    
            # Decrement worker concurrency
            worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
            if worker and worker.current_concurrency > 0:
                worker.current_concurrency -= 1

            # Handle assignment resetting if scraping lease
            if lease.assignment_id:
                assignment = self.db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
                if assignment:
                    assignment.status = "Active"
                    assignment.last_checked = datetime.utcnow()
                    
            # Handle booking task success if booking lease
            if lease.booking_task_id:
                task = self.db.query(BookingTask).filter(BookingTask.id == lease.booking_task_id).first()
                if task:
                    task.status = "SUCCESS"
                    task.active_status = False
            
            log = EventLog(
                source="lease_service",
                worker_id=worker_id,
                assignment_id=lease.assignment_id,
                severity="info",
                event_type="LEASE_COMPLETED",
                payload={"booking_task_id": lease.booking_task_id} if lease.booking_task_id else {}
            )
            self.db.add(log)
            self.db.commit()

    def fail_lease(self, worker_id: str, assignment_id: int):
        lease = self.db.query(Lease).filter(
            Lease.worker_id == worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).filter(
            (Lease.assignment_id == assignment_id) | (Lease.booking_task_id == assignment_id)
        ).first()
        
        if lease:
            lease.status = "Failed"
            
            # Reset PortalAccount status
            if lease.portal_account_id:
                account = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
                if account and account.status == "LEASED":
                    account.status = "READY"
            
            # Reset Proxy status
            if lease.proxy_id:
                proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first()
                if proxy and proxy.status == "LEASED":
                    proxy.status = "READY"
                    
            # Decrement worker concurrency
            worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
            if worker and worker.current_concurrency > 0:
                worker.current_concurrency -= 1

            # Handle assignment resetting if scraping lease
            if lease.assignment_id:
                assignment = self.db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
                if assignment:
                    assignment.status = "Active"
                    assignment.last_checked = datetime.utcnow()
                    
            # Handle booking task retry/failure if booking lease
            if lease.booking_task_id:
                task = self.db.query(BookingTask).filter(BookingTask.id == lease.booking_task_id).first()
                if task:
                    if task.attempts < task.max_attempts:
                        task.status = "PENDING"
                    else:
                        task.status = "FAILED"
                        task.active_status = False
            
            log = EventLog(
                source="lease_service",
                worker_id=worker_id,
                assignment_id=lease.assignment_id,
                severity="error",
                event_type="LEASE_FAILED",
                payload={"booking_task_id": lease.booking_task_id} if lease.booking_task_id else {}
            )
            self.db.add(log)
            self.db.commit()

    def cancel_active_leases(self, assignment_ids: List[int]):
        leases = self.db.query(Lease).filter(
            Lease.assignment_id.in_(assignment_ids),
            Lease.status.in_(["Leased", "Running"])
        ).all()
        for lease in leases:
            lease.status = "Cancelled"
            
            # Reset PortalAccount status
            if lease.portal_account_id:
                account = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
                if account and account.status == "LEASED":
                    account.status = "READY"
            
            # Reset Proxy status
            if lease.proxy_id:
                proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first()
                if proxy and proxy.status == "LEASED":
                    proxy.status = "READY"
                    
            # Decrement worker concurrency
            worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == lease.worker_id).first()
            if worker and worker.current_concurrency > 0:
                worker.current_concurrency -= 1

            if lease.booking_task_id:
                task = self.db.query(BookingTask).filter(BookingTask.id == lease.booking_task_id).first()
                if task:
                    task.status = "PENDING"
            
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

    def abandon_worker_leases(self, worker_id: str):
        active_leases = self.db.query(Lease).filter(
            Lease.worker_id == worker_id,
            Lease.status.in_(["Leased", "Running"])
        ).all()
        for lease in active_leases:
            lease.status = "Abandoned"
            
            # Reset PortalAccount status
            if lease.portal_account_id:
                account = self.db.query(PortalAccount).filter(PortalAccount.id == lease.portal_account_id).first()
                if account and account.status == "LEASED":
                    account.status = "READY"
            
            # Reset Proxy status
            if lease.proxy_id:
                proxy = self.db.query(Proxy).filter(Proxy.id == lease.proxy_id).first()
                if proxy and proxy.status == "LEASED":
                    proxy.status = "READY"
                    
            # Reset assignment status if scraping
            if lease.assignment_id:
                assignment = self.db.query(Assignment).filter(Assignment.id == lease.assignment_id).first()
                if assignment:
                    assignment.status = "Active"
                    
            # Reset booking task status if booking
            if lease.booking_task_id:
                task = self.db.query(BookingTask).filter(BookingTask.id == lease.booking_task_id).first()
                if task and task.status == "CLAIMED":
                    task.status = "PENDING"
                    
            log = EventLog(
                source="lease_service",
                worker_id=worker_id,
                assignment_id=lease.assignment_id,
                severity="warning",
                event_type="LEASE_ABANDONED",
                payload={"reason": "worker_offline", "booking_task_id": lease.booking_task_id} if lease.booking_task_id else {"reason": "worker_offline"}
            )
            self.db.add(log)
        if active_leases:
            self.db.commit()

def get_lease_service(db: Session = Depends(get_db)) -> LeaseService:
    return LeaseService(db)
