import sys
sys.path.append('/app/app')
from models import SessionLocal, SystemSetting, Assignment, WaitlistQueue, Applicant, PortalAccount
from datetime import datetime, timedelta

db = SessionLocal()
# Enable mock slots
setting = db.query(SystemSetting).filter(SystemSetting.key == 'testing.enable_mock_slots').first()
if not setting:
    setting = SystemSetting(key='testing.enable_mock_slots', value='true', description='Enable mock slots for testing')
    db.add(setting)
else:
    setting.value = 'true'

# Ensure there is an active account
account = db.query(PortalAccount).first()
if account:
    account.status = 'READY'
    account.can_scrape = True
    account.can_book = True

# Create a test assignment
assignment = db.query(Assignment).first()
if not assignment:
    assignment = Assignment(
        provider='GVC',
        visa_center='138',
        date_from=datetime.utcnow().strftime('%d/%m/%Y'),
        date_to=(datetime.utcnow() + timedelta(days=30)).strftime('%d/%m/%Y'),
        polling_interval=300,
        priority=1,
        status='Active'
    )
    db.add(assignment)
    db.commit()
else:
    assignment.status = 'Active'

# Create a test applicant
applicant = db.query(Applicant).first()
if not applicant:
    applicant = Applicant(
        tenant_id=1,
        firstname='John',
        surname='Doe',
        passportnumber='A1234567',
        dateofbirth='01/01/1990',
        nationality='PK',
        gender='MALE',
        passport_expiry='01/01/2030',
        email='test@example.com',
        phone_prefix='+92',
        phone_number='3001234567'
    )
    db.add(applicant)
    db.commit()

# Create a waitlist queue entry for this applicant to trigger booking task
waitlist = db.query(WaitlistQueue).first()
if not waitlist:
    waitlist = WaitlistQueue(
        tenant_id=1,
        applicant_id=applicant.id,
        visa_center='138',
        status='QUEUED',
        priority=1
    )
    db.add(waitlist)

db.commit()
print('Test data setup complete.')
