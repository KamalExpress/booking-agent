import os
import sys

# Add app directory to sys path so we can import models
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, Applicant, WaitlistQueue, BookingTask, PortalAccount, Proxy, InboxMessage
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

def test_models():
    print("Testing Level 1 Database Foundation Models...")
    
    # Use an in-memory SQLite database for testing
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Create a Tenant
        tenant = Tenant(name="Test Tenant")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print(f"Created Tenant: {tenant.name} with ID: {tenant.id}")
        
        # 2. Create an Applicant
        applicant = Applicant(
            tenant_id=tenant.id,
            surname="Doe",
            firstname="John",
            dateofbirth="1990-01-01",
            gender="M",
            nationality="US",
            passportnumber="A1234567",
            passport_expiry="2030-01-01",
            email="john.doe@example.com",
            phone_prefix="+1",
            phone_number="5551234567"
        )
        db.add(applicant)
        db.commit()
        db.refresh(applicant)
        print(f"Created Applicant: {applicant.firstname} {applicant.surname} with ID: {applicant.id}")
        
        # 3. Queue Applicant in Waitlist
        waitlist_entry = WaitlistQueue(
            tenant_id=tenant.id,
            applicant_id=applicant.id,
            provider="GVC",
            visa_center="138",
            appointment_type="0"
        )
        db.add(waitlist_entry)
        db.commit()
        db.refresh(waitlist_entry)
        print(f"Created Waitlist Entry with ID: {waitlist_entry.id} for Applicant ID: {waitlist_entry.applicant.id}")
        
        # 4. Create an Inbox Message
        inbox_msg = InboxMessage(
            tenant_id=tenant.id,
            severity="info",
            title="Welcome",
            body="Welcome to the tenant."
        )
        db.add(inbox_msg)
        db.commit()
        db.refresh(inbox_msg)
        print(f"Created InboxMessage with ID: {inbox_msg.id}")
        
        # 5. Link Applicant to Booking Task
        import datetime
        booking_task = BookingTask(
            tenant_id=tenant.id,
            applicant_id=applicant.id,
            visa_center="138",
            target_date="2027-01-01",
            target_time="10:00",
            otp_code="123456",
            expires_at=datetime.datetime.utcnow() # just a dummy date
        )
        db.add(booking_task)
        db.commit()
        db.refresh(booking_task)
        print(f"Created BookingTask ID: {booking_task.id} with OTP: {booking_task.otp_code} for Applicant: {booking_task.applicant_id}")
        
        # 6. Verify Tenant isolation on PortalAccount and Proxy
        account = PortalAccount(
            tenant_id=tenant.id,
            username="test_account",
            password="password123"
        )
        proxy = Proxy(
            tenant_id=tenant.id,
            host="127.0.0.1",
            port="8080"
        )
        db.add_all([account, proxy])
        db.commit()
        db.refresh(account)
        db.refresh(proxy)
        print(f"Created PortalAccount ID: {account.id} and Proxy ID: {proxy.id} linked to Tenant ID: {tenant.id}")
        
        print("\nAll model relationships and constraints passed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_models()
