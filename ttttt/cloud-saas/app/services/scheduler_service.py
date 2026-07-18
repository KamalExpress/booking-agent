from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import Depends

from app.models import (
    WorkerNode, PortalAccount, Proxy, Assignment, BookingTask, 
    Lease, SchedulerDecision, EventLog, get_db
)
from app.services.scoring_policy import ScoringPolicy

class SchedulerService:
    def __init__(self, db: Session):
        self.db = db
        
    def _log_decision(self, worker_id: str, decision_type: str, reason: str, 
                      assignment_id: int = None, booking_task_id: int = None, 
                      account_id: int = None, proxy_id: int = None):
        decision = SchedulerDecision(
            worker_id=worker_id,
            decision_type=decision_type,
            decision_reason=reason,
            selected_assignment_id=assignment_id,
            selected_booking_task_id=booking_task_id,
            selected_account_id=account_id,
            selected_proxy_id=proxy_id
        )
        self.db.add(decision)
        self.db.commit()

    def get_next_lease(self, worker_id: str) -> Lease:
        """
        Main entry point for a worker requesting work.
        1. Try to assign a BookingTask first (priority)
        2. If none, try to assign a scraping Assignment
        """
        worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
        if not worker:
            return None

        # 1. Booking Phase
        if worker.can_book:
            lease = self._try_schedule_booking(worker)
            if lease:
                return lease

        # 2. Scraping Phase
        if worker.can_scrape:
            lease = self._try_schedule_scraping(worker)
            if lease:
                return lease
                
        # 3. No Work Found
        self._log_decision(worker.worker_id, "NO_ASSIGNMENT", "No scraping or booking tasks available.")
        return None

    def _try_schedule_booking(self, worker: WorkerNode) -> Lease:
        now = ScoringPolicy.get_utcnow()
        # Find a pending booking task
        task = self.db.query(BookingTask).filter(
            BookingTask.status == "PENDING",
            BookingTask.expires_at > now
        ).order_by(BookingTask.priority.desc(), BookingTask.created_at.asc()).first()
        
        if not task:
            return None
            
        if ScoringPolicy.score_worker_for_booking(worker, task) < 0:
            return None

        # Find best account
        accounts = self.db.query(PortalAccount).filter(PortalAccount.supports_booking == True).all()
        best_account = None
        best_account_score = -1
        
        for account in accounts:
            score = ScoringPolicy.score_account(account, task.provider)
            if score > best_account_score:
                best_account_score = score
                best_account = account
                
        if not best_account:
            self._log_decision(worker.worker_id, "NO_READY_ACCOUNT", "No capable booking account available", booking_task_id=task.id)
            return None

        # Find best proxy
        proxies = self.db.query(Proxy).filter(Proxy.supports_booking == True).all()
        best_proxy = None
        best_proxy_score = -1
        
        for proxy in proxies:
            score = ScoringPolicy.score_proxy(proxy)
            if score > best_proxy_score:
                best_proxy_score = score
                best_proxy = proxy
                
        if not best_proxy:
            self._log_decision(worker.worker_id, "NO_READY_PROXY", "No capable booking proxy available", booking_task_id=task.id)
            return None

        # Create lease
        lease = Lease(
            worker_id=worker.worker_id,
            booking_task_id=task.id,
            portal_account_id=best_account.id,
            proxy_id=best_proxy.id,
            expires_at=now + timedelta(minutes=10),
            status="Leased"
        )
        
        task.status = "CLAIMED"
        task.attempts += 1
        
        best_account.status = "LEASED"
        best_proxy.status = "LEASED"
        
        worker.current_concurrency += 1
        
        self.db.add(lease)
        self._log_decision(
            worker.worker_id, "SUCCESS", "Leased booking task", 
            booking_task_id=task.id, account_id=best_account.id, proxy_id=best_proxy.id
        )
        self.db.commit()
        return lease

    def _try_schedule_scraping(self, worker: WorkerNode) -> Lease:
        now = ScoringPolicy.get_utcnow()
        # Find due assignments
        assignments = self.db.query(Assignment).filter(
            Assignment.status == "Active"
        ).order_by(Assignment.priority.desc()).all()
        
        due_assignment = None
        for a in assignments:
            if not a.last_checked or (now - a.last_checked).total_seconds() > a.polling_interval:
                if ScoringPolicy.score_worker_for_scraping(worker, a) >= 0:
                    due_assignment = a
                    break
                    
        if not due_assignment:
            return None
            
        # Find best account
        accounts = self.db.query(PortalAccount).filter(PortalAccount.supports_scraping == True).all()
        best_account = None
        best_account_score = -1
        
        for account in accounts:
            score = ScoringPolicy.score_account(account, due_assignment.provider)
            if score > best_account_score:
                best_account_score = score
                best_account = account
                
        if not best_account:
            self._log_decision(worker.worker_id, "NO_READY_ACCOUNT", "No capable scraping account available", assignment_id=due_assignment.id)
            return None

        # Find best proxy
        proxies = self.db.query(Proxy).filter(Proxy.supports_scraping == True).all()
        best_proxy = None
        best_proxy_score = -1
        
        for proxy in proxies:
            score = ScoringPolicy.score_proxy(proxy)
            if score > best_proxy_score:
                best_proxy_score = score
                best_proxy = proxy
                
        if not best_proxy:
            self._log_decision(worker.worker_id, "NO_READY_PROXY", "No capable scraping proxy available", assignment_id=due_assignment.id)
            return None

        # Create lease
        lease = Lease(
            worker_id=worker.worker_id,
            assignment_id=due_assignment.id,
            portal_account_id=best_account.id,
            proxy_id=best_proxy.id,
            expires_at=now + timedelta(minutes=5),
            status="Leased"
        )
        
        due_assignment.last_checked = now
        
        best_account.status = "LEASED"
        best_proxy.status = "LEASED"
        
        worker.current_concurrency += 1
        
        self.db.add(lease)
        self._log_decision(
            worker.worker_id, "SUCCESS", "Leased scraping task", 
            assignment_id=due_assignment.id, account_id=best_account.id, proxy_id=best_proxy.id
        )
        self.db.commit()
        return lease

    def handle_event(self, event_type: str, lease: Lease, details: dict = None):
        """Translates technical events into account/proxy cooldowns."""
        now = ScoringPolicy.get_utcnow()
        account = self.db.query(PortalAccount).filter_by(id=lease.portal_account_id).first()
        proxy = self.db.query(Proxy).filter_by(id=lease.proxy_id).first()
        
        if event_type == "LOGIN_FAILED":
            if account:
                account.failure_count += 1
                account.last_failure = now
                account.cooldown_until = now + timedelta(minutes=30)
        elif event_type == "CAPTCHA_FAILED":
            if proxy:
                proxy.failure_count += 1
                proxy.cooldown_until = now + timedelta(minutes=10)
        elif event_type == "PROXY_TIMEOUT":
            if proxy:
                proxy.failure_count += 1
                proxy.cooldown_until = now + timedelta(minutes=15)
        elif event_type == "RATE_LIMITED":
            if account:
                account.failure_count += 1
                account.cooldown_until = now + timedelta(minutes=60)
            if proxy:
                proxy.failure_count += 1
                proxy.cooldown_until = now + timedelta(minutes=60)
        elif event_type == "LOGIN_SUCCESS":
            if account:
                account.last_login = now
                account.last_success = now
                account.failure_count = 0
            if proxy:
                proxy.last_used = now
                proxy.failure_count = 0
        
        self.db.commit()

def get_scheduler_service(db: Session = Depends(get_db)) -> SchedulerService:
    return SchedulerService(db)
