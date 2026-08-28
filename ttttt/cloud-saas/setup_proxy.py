import sys
sys.path.append('/app/app')
from models import SessionLocal, Proxy

db = SessionLocal()
proxy = db.query(Proxy).first()
if not proxy:
    proxy = Proxy(
        host="127.0.0.1",
        port=8080,
        username="dummyuser",
        password="dummypass",
        tenant_id=1,
        status="READY",
        supports_scraping=True,
        supports_booking=True
    )
    db.add(proxy)
else:
    proxy.status = "READY"
    proxy.supports_scraping = True
    proxy.supports_booking = True

db.commit()
print('Added test proxy.')
