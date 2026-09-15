import os
import sys
import unittest
from datetime import datetime, timedelta

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from models import Base, Tenant, Applicant, WaitlistQueue, BookingTask, PortalAccount, Proxy, WorkerNode, Lease
from services.lease_service import LeaseService
from services.scheduler_service import SchedulerService

class TestQueueLifecycle(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        # Seed Tenant & Applicant
        self.tenant = Tenant(name="Kamal Express", is_active=True)
        self.db.add(self.tenant)
        self.db.commit()
        
        self.applicant = Applicant(
            tenant_id=self.tenant.id,
            surname="Raza",
            firstname="Ali",
            phone_number="923345112969",
            dateofbirth="1990-01-01",
            gender="M",
            nationality="PK",
            passportnumber="EG9903901",
            passport_expiry="2030-01-01",
            email="ali@example.com",
            phone_prefix="+92"
        )
        self.db.add(self.applicant)
        self.db.commit()
        
    def tearDown(self):
        self.db.close()
        
    def test_waitlist_self_healing_on_stuck_dispatched(self):
        lease_svc = LeaseService(self.db)
        
        # 1. Create a queue entry stuck in DISPATCHED with no active task
        wq = WaitlistQueue(
            tenant_id=self.tenant.id,
            applicant_id=self.applicant.id,
            visa_center="138",
            status="DISPATCHED",
            priority=10
        )
        self.db.add(wq)
        self.db.commit()
        
        # 2. Run expire_stale_leases self-healing
        lease_svc.expire_stale_leases()
        
        self.db.refresh(wq)
        self.assertEqual(wq.status, "PENDING", "Orphan DISPATCHED queue entry should be self-healed to PENDING")
        
    def test_waitlist_sync_on_task_success(self):
        lease_svc = LeaseService(self.db)
        
        wq = WaitlistQueue(tenant_id=self.tenant.id, applicant_id=self.applicant.id, visa_center="138", status="DISPATCHED")
        task = BookingTask(
            tenant_id=self.tenant.id,
            applicant_id=self.applicant.id,
            visa_center="138",
            target_date="15/09/2026",
            target_time="10:00",
            expires_at=datetime.utcnow() + timedelta(hours=2),
            status="CLAIMED",
            attempts=1,
            max_attempts=3
        )
        self.db.add_all([wq, task])
        self.db.commit()
        
        worker = WorkerNode(worker_id="test_booker", secret_hash="test_hash", can_book=True, last_heartbeat=datetime.utcnow())
        lease = Lease(worker_id="test_booker", booking_task_id=task.id, status="Leased", expires_at=datetime.utcnow()+timedelta(minutes=5))
        self.db.add_all([worker, lease])
        self.db.commit()
        
        # Complete lease
        lease_svc.complete_lease(worker_id="test_booker", assignment_id=task.id)
        
        self.db.refresh(wq)
        self.db.refresh(task)
        self.assertEqual(task.status, "SUCCESS")
        self.assertEqual(wq.status, "BOOKED", "WaitlistQueue should be synchronized to BOOKED when task completes")
        
    def test_waitlist_sync_on_task_failure_exhausted(self):
        lease_svc = LeaseService(self.db)
        
        wq = WaitlistQueue(tenant_id=self.tenant.id, applicant_id=self.applicant.id, visa_center="138", status="DISPATCHED")
        task = BookingTask(
            tenant_id=self.tenant.id,
            applicant_id=self.applicant.id,
            visa_center="138",
            target_date="15/09/2026",
            target_time="10:00",
            expires_at=datetime.utcnow() + timedelta(hours=2),
            status="CLAIMED",
            attempts=3, # Max reached
            max_attempts=3
        )
        self.db.add_all([wq, task])
        self.db.commit()
        
        worker = WorkerNode(worker_id="test_booker", secret_hash="test_hash", can_book=True, last_heartbeat=datetime.utcnow())
        lease = Lease(worker_id="test_booker", booking_task_id=task.id, status="Leased", expires_at=datetime.utcnow()+timedelta(minutes=5))
        self.db.add_all([worker, lease])
        self.db.commit()
        
        # Fail lease
        lease_svc.fail_lease(worker_id="test_booker", assignment_id=task.id, reason="WAF_CHALLENGE")
        
        self.db.refresh(wq)
        self.db.refresh(task)
        self.assertEqual(task.status, "FAILED")
        self.assertEqual(wq.status, "FAILED", "WaitlistQueue should be synchronized to FAILED when task exhausts attempts")

if __name__ == "__main__":
    unittest.main()
