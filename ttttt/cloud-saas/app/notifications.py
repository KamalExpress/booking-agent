import os
import tempfile
import logging
from sqlalchemy.orm import Session
from models import PushSubscription

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "BOJviVyqeMuXRl9-4a_iJrH67TKwCjV7N4YZs-tZ63ZBHOtqksgujIA_0yMiDaC_EAt-wUJ4YNJN4vZMoBMeuzs")
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
    from models import SystemSetting, EventLog, User
    
    detailed_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.detailed_push_logging").first()
    detailed_logging = detailed_setting.value.lower() == 'true' if (detailed_setting and detailed_setting.value) else False
    
    query = db.query(PushSubscription, User).join(User, PushSubscription.user_id == User.id)
    if user_ids is not None:
        query = query.filter(PushSubscription.user_id.in_(user_ids))
    
    subs = query.all()
    if not subs:
        return 0
        
    logger.info(f"Sending push notification to {len(subs)} endpoints...")
    success_count = 0
    
    success_by_tenant = {}
    failure_by_tenant = {}
    
    for sub, user in subs:
        t_id = user.tenant_id
        if t_id not in success_by_tenant:
            success_by_tenant[t_id] = 0
            failure_by_tenant[t_id] = 0
            
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
            success_by_tenant[t_id] += 1
            
            if detailed_logging:
                db.add(EventLog(
                    event_type="PUSH_SENT_DEVICE",
                    severity="info",
                    payload={"tenant_id": t_id, "user_id": user.id, "endpoint": sub.endpoint[:30], "status": "success", "title": title}
                ))
        except Exception as e:
            failure_by_tenant[t_id] += 1
            logger.error(f"Failed to push to endpoint {sub.endpoint[:30]}... Error: {str(e)}")
            if detailed_logging:
                db.add(EventLog(
                    event_type="PUSH_SENT_DEVICE",
                    severity="error",
                    payload={"tenant_id": t_id, "user_id": user.id, "endpoint": sub.endpoint[:30], "status": "failed", "error": str(e), "title": title}
                ))
                
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in [404, 410]:
                    logger.info(f"Endpoint {sub.endpoint[:30]} is dead ({e.response.status_code}). Cleaning up.")
                    try:
                        db.delete(sub)
                    except:
                        pass
                        
    for t_id in success_by_tenant:
        sc = success_by_tenant[t_id]
        fc = failure_by_tenant[t_id]
        if sc > 0 or fc > 0:
            db.add(EventLog(
                event_type="PUSH_SENT",
                severity="info",
                payload={"tenant_id": t_id, "success_count": sc, "failure_count": fc, "title": title, "body": body}
            ))
            
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit push notification logs: {e}")
        db.rollback()
            
    return success_count
