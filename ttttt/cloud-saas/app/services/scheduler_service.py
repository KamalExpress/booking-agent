from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import Depends

from typing import Any, Optional

try:
    from models import (
        WorkerNode, PortalAccount, Proxy, Assignment, BookingTask, 
        Lease, SchedulerDecision, EventLog, WaitlistQueue, Applicant, get_db
    )
    from services.scoring_policy import ScoringPolicy
except ImportError:
    from app.models import (
        WorkerNode, PortalAccount, Proxy, Assignment, BookingTask, 
        Lease, SchedulerDecision, EventLog, WaitlistQueue, Applicant, get_db
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
        worker = self.db.query(WorkerNode).filter(
            WorkerNode.worker_id == worker_id,
            or_(WorkerNode.is_archived == False, WorkerNode.is_archived == None)
        ).first()
        if not worker:
            return None

        # Automatically expire stale leases to free up locked accounts/proxies
        from app.services.lease_service import LeaseService
        LeaseService(self.db).expire_stale_leases()

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
                
        return None

    def _try_schedule_booking(self, worker: WorkerNode) -> Lease:
        now = ScoringPolicy.get_utcnow()
        # Find a pending booking task
        task = self.db.query(BookingTask).filter(
            BookingTask.status == "PENDING",
            BookingTask.expires_at > now
        ).order_by(BookingTask.priority.desc(), BookingTask.created_at.asc()).with_for_update(skip_locked=True).first()
        
        if not task:
            return None
            
        if ScoringPolicy.score_worker_for_booking(worker, task) < 0:
            return None

        # Find best account
        accounts = self.db.query(PortalAccount).filter(
            PortalAccount.supports_booking == True,
            or_(PortalAccount.tenant_id == task.tenant_id, PortalAccount.tenant_id == None)
        ).all()
        best_account = None
        best_account_score = -1
        
        for account in accounts:
            # Enforce SIM/phone concurrency: if another account shares the same phone_number and is currently LEASED, skip it
            if account.phone_number:
                active_sim_lease = self.db.query(PortalAccount).filter(
                    PortalAccount.phone_number == account.phone_number,
                    PortalAccount.status == "LEASED",
                    PortalAccount.id != account.id
                ).first()
                if active_sim_lease:
                    continue
                    
            score = ScoringPolicy.score_account(account, task.provider)
            if score > best_account_score:
                best_account_score = score
                best_account = account
                
        if not best_account:
            self._log_decision(worker.worker_id, "NO_READY_ACCOUNT", "No capable booking account available", booking_task_id=task.id)
            return None

        # Concurrency verification lock
        locked_account = self.db.query(PortalAccount).filter(
            PortalAccount.id == best_account.id,
            PortalAccount.status == "READY"
        ).with_for_update(skip_locked=True).first()
        
        if not locked_account:
            # Someone else took it while we were scoring
            return None
            
        best_account = locked_account

        # Find best proxy
        proxies = self.db.query(Proxy).filter(
            Proxy.supports_booking == True,
            or_(Proxy.tenant_id == task.tenant_id, Proxy.tenant_id == None)
        ).all()
        best_proxy = None
        best_proxy_score = -1
        
        for proxy in proxies:
            score = ScoringPolicy.score_proxy(proxy, task.provider)
            if score > best_proxy_score:
                best_proxy_score = score
                best_proxy = proxy
                
        if not best_proxy:
            self._log_decision(worker.worker_id, "NO_READY_PROXY", "No capable booking proxy available", booking_task_id=task.id)
            return None

        # Concurrency verification lock
        locked_proxy = self.db.query(Proxy).filter(
            Proxy.id == best_proxy.id,
            Proxy.status == "READY"
        ).with_for_update(skip_locked=True).first()
        
        if not locked_proxy:
            return None
            
        best_proxy = locked_proxy

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
        # Find due assignments (we lock them to prevent concurrent threads from scoring the same assignment)
        assignments = self.db.query(Assignment).filter(
            Assignment.status == "Active"
        ).order_by(Assignment.priority.desc()).with_for_update(skip_locked=True).all()
        
        due_assignment = None
        for a in assignments:
            if not a.last_checked or (now - a.last_checked).total_seconds() > a.polling_interval:
                if ScoringPolicy.score_worker_for_scraping(worker, a) >= 0:
                    due_assignment = a
                    break
                    
        if not due_assignment:
            self._log_decision(worker.worker_id, "NO_ASSIGNMENT", "No scraping or booking tasks available.")
            return None
            
        # Find best account (allow global accounts or any registered scraping accounts)
        accounts = self.db.query(PortalAccount).filter(
            PortalAccount.supports_scraping == True,
            or_(PortalAccount.is_archived == False, PortalAccount.is_archived == None)
        ).all()
        best_account = None
        best_account_score = -1
        
        for account in accounts:
            score = ScoringPolicy.score_account(account, due_assignment.provider)
            if score > best_account_score:
                best_account_score = score
                best_account = account
                
        if not best_account:
            matching_provider_accounts = [a for a in accounts if a.provider and a.provider.strip().upper() == due_assignment.provider.strip().upper()]
            if not matching_provider_accounts:
                reason = f"No portal account registered for provider '{due_assignment.provider}' with scraping enabled."
            else:
                statuses = set(a.status for a in matching_provider_accounts)
                reason = f"Account(s) for '{due_assignment.provider}' exist, but none are READY (current status: {', '.join(statuses)})."
                
            self._log_decision(
                worker.worker_id, 
                "NO_READY_ACCOUNT", 
                reason, 
                assignment_id=due_assignment.id
            )
            return None

        # Concurrency verification lock
        locked_account = self.db.query(PortalAccount).filter(
            PortalAccount.id == best_account.id,
            PortalAccount.status == "READY"
        ).with_for_update(skip_locked=True).first()
        
        if not locked_account:
            return None
            
        best_account = locked_account

        # Find best proxy
        proxies = self.db.query(Proxy).filter(
            Proxy.supports_scraping == True
        ).all()
        best_proxy = None
        best_proxy_score = -1
        
        for proxy in proxies:
            score = ScoringPolicy.score_proxy(proxy, due_assignment.provider)
            if score > best_proxy_score:
                best_proxy_score = score
                best_proxy = proxy
                
        if not best_proxy:
            self._log_decision(worker.worker_id, "NO_READY_PROXY", "No capable scraping proxy available", assignment_id=due_assignment.id)
            return None

        # Concurrency verification lock
        locked_proxy = self.db.query(Proxy).filter(
            Proxy.id == best_proxy.id,
            Proxy.status == "READY"
        ).with_for_update(skip_locked=True).first()
        
        if not locked_proxy:
            return None
            
        best_proxy = locked_proxy

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

    def auto_dispatch_queue(self, visa_center: str, slots: Any = None, assignment_id: int = None, target_date: str = None):
        import logging
        logger = logging.getLogger(__name__)
        now = ScoringPolicy.get_utcnow()
        if isinstance(slots, int):
            slots = [{"id": None, "starttime": "00:00"}] * slots
        elif not slots or not isinstance(slots, list):
            slots = [{"id": None, "starttime": "00:00"}]
            
        slot_count = len(slots)
        target_date = target_date or datetime.utcnow().strftime("%Y-%m-%d")
        logger.info(f"auto_dispatch_queue invoked: visa_center={visa_center}, slot_count={slot_count}, target_date={target_date}")
        
        # 0. Expire old uncompleted booking tasks so they don't lock applicants forever
        stale_tasks = self.db.query(BookingTask).filter(
            BookingTask.status.in_(["PENDING", "CLAIMED"]),
            BookingTask.expires_at < now
        ).all()
        if stale_tasks:
            logger.info(f"Expiring {len(stale_tasks)} stale booking tasks that exceeded TTL.")
            for st in stale_tasks:
                st.status = "EXPIRED"
                st.active_status = False
            self.db.flush()
        
        # 1. Get PENDING waitlist entries for this visa center, ordered by priority
        entries = self.db.query(WaitlistQueue).join(Applicant).filter(
            WaitlistQueue.status == "PENDING",
            WaitlistQueue.visa_center == str(visa_center)
        ).order_by(WaitlistQueue.priority.desc(), WaitlistQueue.created_at.asc()).all()
        
        logger.info(f"Found {len(entries)} PENDING waitlist queue entries for center {visa_center}")
        if not entries:
            return 0
            
        dispatched_count = 0
        batch_locked_phones = set()
        for entry in entries:
            if dispatched_count >= slot_count:
                break
                
            # 2. Prevent OTP race condition: check if applicant's phone number is actively locked in DB or in current batch
            applicant_phone = entry.applicant.phone_number
            if applicant_phone in batch_locked_phones:
                logger.info(f"Skipping applicant #{entry.applicant_id} ({applicant_phone}): already locked in current batch")
                continue
                
            active_locks = self.db.query(BookingTask).join(Applicant, BookingTask.applicant_id == Applicant.id).filter(
                BookingTask.status.in_(["PENDING", "CLAIMED"]),
                Applicant.phone_number == applicant_phone
            ).first()
            
            if active_locks:
                logger.info(f"Skipping applicant #{entry.applicant_id} ({applicant_phone}): actively locked by BookingTask #{active_locks.id} (status={active_locks.status})")
                continue
                
            # 3. Generate BookingTask
            slot = slots[dispatched_count]
            slot_time = slot.get("starttime", "00:00") if isinstance(slot, dict) else "00:00"
            
            try:
                task = BookingTask(
                    assignment_id=assignment_id,
                    tenant_id=entry.tenant_id,
                    applicant_id=entry.applicant_id,
                    provider=entry.provider,
                    visa_center=entry.visa_center,
                    target_date=target_date, 
                    target_time=slot_time,
                    slot_payload=slot if isinstance(slot, dict) else {},
                    priority=entry.priority,
                    expires_at=now + timedelta(hours=2)
                )
                self.db.add(task)
                
                entry.status = "BOOKED"
                batch_locked_phones.add(applicant_phone)
                self.db.flush() # Flush so subsequent queries in this loop see the new lock
                dispatched_count += 1
                logger.info(f"Successfully created BookingTask #{task.id} for applicant #{entry.applicant_id} ({entry.applicant.firstname} {entry.applicant.surname}) at center {entry.visa_center}")
            except Exception as task_err:
                logger.error(f"Failed to create BookingTask for applicant #{entry.applicant_id}: {task_err}")
                self.db.rollback()
                break
            
        if dispatched_count > 0:
            self.db.commit()
            
        return dispatched_count

    def handle_event(self, event_type: str, lease: Lease, details: dict = None):
        """Translates technical events into account/proxy cooldowns."""
        now = ScoringPolicy.get_utcnow()
        account = self.db.query(PortalAccount).filter_by(id=lease.portal_account_id).first() if lease.portal_account_id else None
        proxy = self.db.query(Proxy).filter_by(id=lease.proxy_id).first() if lease.proxy_id else None
        
        if event_type == "SLOT_FOUND":
            if account:
                account.last_success = now
                account.failure_count = 0
            if proxy:
                proxy.last_used = now
                proxy.failure_count = 0
                
        elif event_type == "LOGIN_FAILED":
            if account:
                account.failure_count += 1
                account.last_failure = now
                account.cooldown_until = now + timedelta(minutes=30)
        elif event_type == "CAPTCHA_FAILED":
            if proxy:
                proxy.failure_count += 1
                proxy.cooldown_until = now + timedelta(minutes=10)
        elif event_type in ["PROXY_TIMEOUT", "PROXY_BANNED"]:
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
