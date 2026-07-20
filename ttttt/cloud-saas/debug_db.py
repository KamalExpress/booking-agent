import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from models import SessionLocal, ScraperAccount, Assignment, Lease

db = SessionLocal()

print("--- Scraper Accounts ---")
for acc in db.query(ScraperAccount).all():
    print(f"Account {acc.id}: {acc.username} - Status: {acc.status}")

print("\n--- Assignments ---")
for asm in db.query(Assignment).all():
    print(f"Assignment {asm.id}: Account ID {asm.scraper_account_id} - Status: {asm.status} - Last Checked: {asm.last_checked} - Interval: {asm.polling_interval}")

print("\n--- Leases ---")
for lease in db.query(Lease).all():
    print(f"Lease {lease.id}: Assignment {lease.assignment_id} - Worker {lease.worker_id} - Status: {lease.status} - Expires: {lease.expires_at}")

db.close()
