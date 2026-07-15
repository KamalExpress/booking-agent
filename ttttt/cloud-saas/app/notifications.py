import os
import tempfile
import logging
from sqlalchemy.orm import Session
from models import PushSubscription

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "BPiJHAyOHhUN-lfs6ZZbCsJxG0044_Hk7w2ezWWKxRW1NPPCq4OdT_WGakDn6__jhpPtrc0nWLtpYThZk3fIBOM")
_vapid_env = os.getenv("VAPID_PRIVATE_KEY")
if _vapid_env and "-----BEGIN PRIVATE KEY-----" in _vapid_env:
    # pywebpush requires a file path for PEM keys, not the raw string
    pem_data = _vapid_env.replace('\\n', '\n')
    temp_pem_path = os.path.join(tempfile.gettempdir(), "vapid_private_key.pem")
    with open(temp_pem_path, "w") as f:
        f.write(pem_data)
    VAPID_PRIVATE_KEY = temp_pem_path
elif _vapid_env:
    VAPID_PRIVATE_KEY = _vapid_env.replace('\\n', '\n')
else:
    VAPID_PRIVATE_KEY = os.path.join(os.path.dirname(os.path.dirname(__file__)), "private_key.pem")


def send_push_notification(db: Session, title: str, body: str, user_ids: list = None):
    from pywebpush import webpush
    
    query = db.query(PushSubscription)
    if user_ids is not None:
        query = query.filter(PushSubscription.user_id.in_(user_ids))
    
    subs = query.all()
    if not subs:
        return 0
        
    logger.info(f"Sending push notification to {len(subs)} endpoints...")
    success_count = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                },
                data=f'{{"title":"{title}","body":"{body}","url":"/"}}',
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@samwebdevs.dpdns.org"}
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to push to endpoint {sub.endpoint[:30]}... Error: {str(e)}")
            
    return success_count
