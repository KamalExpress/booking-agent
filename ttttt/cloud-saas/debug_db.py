import os
import sys

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'ttttt', 'cloud-saas', 'app'))

from models import SessionLocal, User, Tenant, PushSubscription

db = SessionLocal()

print("--- Tenants ---")
for t in db.query(Tenant).all():
    print(f"Tenant {t.id}: {t.name}")

print("\n--- Users ---")
for u in db.query(User).all():
    print(f"User {u.id}: {u.email} (Tenant {u.tenant_id})")

print("\n--- Push Subscriptions ---")
for s in db.query(PushSubscription).all():
    print(f"Sub {s.id}: User {s.user_id} - Endpoint {s.endpoint[:30]}...")

db.close()
