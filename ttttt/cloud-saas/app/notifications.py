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


def send_push_notification(db: Session, title: str, body: str, user_ids: list = None, visa_center_id: str = None):
    from pywebpush import webpush
    from models import SystemSetting, EventLog, User
    from core.branding import get_env_branding
    
    env_branding = get_env_branding()
    prefixed_title = f"{env_branding.notification_prefix}{title}"
    
    detailed_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.detailed_push_logging").first()
    detailed_logging = detailed_setting.value.lower() == 'true' if (detailed_setting and detailed_setting.value) else False
    
    # Query all push subscriptions across all users and devices
    query = db.query(PushSubscription, User).outerjoin(User, PushSubscription.user_id == User.id)
    if user_ids is not None:
        query = query.filter(PushSubscription.user_id.in_(user_ids))
    
    subs = query.all()
    if not subs:
        return 0
        
    logger.info(f"Broadcasting push notification to {len(subs)} subscriber endpoints...")
    success_count = 0
    
    success_by_tenant = {}
    failure_by_tenant = {}
    
    for sub, user in subs:
        if visa_center_id and user and user.preferences:
            muted_centers = user.preferences.get("muted_visa_centers", [])
            if str(visa_center_id) in muted_centers:
                continue
                
        t_id = user.tenant_id if user else 1
        if t_id not in success_by_tenant:
            success_by_tenant[t_id] = 0
            failure_by_tenant[t_id] = 0
            
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                },
                data=f'{{"title":"{prefixed_title}","body":"{body}","url":"/"}}',
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


def send_booking_confirmed_push(
    db: Session,
    task,
    applicant,
    reference_number: str = None
):
    """
    Tenant-scoped push notification for booking confirmation:
    - SuperAdmin + Target Tenant Admin & Staff receive full details.
    - Other Tenants receive half-masked details (marketing hook).
    """
    from pywebpush import webpush
    from models import PushSubscription, User, RoleEnum, EventLog, SystemSetting
    from core.branding import get_env_branding
    
    env_branding = get_env_branding()
    target_tenant_id = task.tenant_id if task else (applicant.tenant_id if applicant else 1)
    visa_center_id = task.visa_center if task else "138"
    
    # 1. Prepare Full Details
    first_name = applicant.firstname if applicant else "Applicant"
    last_name = applicant.surname if applicant else ""
    full_name = f"{first_name} {last_name}".strip()
    passport = applicant.passportnumber if applicant else ""
    
    full_title = f"{env_branding.notification_prefix}🎉 Booking Confirmed!"
    full_body = f"Appointment confirmed for {full_name} ({passport}) at Center {visa_center_id}. Ref: {reference_number or 'Confirmed'}"
    
    # 2. Prepare Masked Marketing Details
    if last_name:
        masked_name = f"{first_name} {last_name[0]}***"
    else:
        masked_name = f"{first_name[:3]}***" if len(first_name) > 3 else f"{first_name}***"
        
    if len(passport) >= 6:
        masked_passport = f"{passport[:4]}***{passport[-2:]}"
    elif len(passport) >= 3:
        masked_passport = f"{passport[:2]}***"
    else:
        masked_passport = "***"
        
    marketing_title = f"{env_branding.notification_prefix}⚡ Slot Secured!"
    marketing_body = f"Greece Visa slot booked for {masked_name} (PP: {masked_passport}) at Center {visa_center_id}. Auto-booking active!"
    
    detailed_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.detailed_push_logging").first()
    detailed_logging = detailed_setting.value.lower() == 'true' if (detailed_setting and detailed_setting.value) else False
    
    subs = db.query(PushSubscription, User).outerjoin(User, PushSubscription.user_id == User.id).all()
    if not subs:
        return 0
        
    logger.info(f"Broadcasting tenant-scoped booking push to {len(subs)} subscriber endpoints...")
    success_count = 0
    success_by_tenant = {}
    failure_by_tenant = {}
    
    for sub, user in subs:
        if user and user.preferences:
            muted_centers = user.preferences.get("muted_visa_centers", [])
            if str(visa_center_id) in muted_centers:
                continue
                
        user_tenant_id = user.tenant_id if user else 1
        user_role = user.role if user else RoleEnum.STAFF
        
        # SuperAdmin or Member of Target Tenant gets Full Details
        is_privileged = (user_role == RoleEnum.SUPER_ADMIN) or (user_tenant_id == target_tenant_id)
        
        notif_title = full_title if is_privileged else marketing_title
        notif_body = full_body if is_privileged else marketing_body
        
        if user_tenant_id not in success_by_tenant:
            success_by_tenant[user_tenant_id] = 0
            failure_by_tenant[user_tenant_id] = 0
            
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                },
                data=f'{{"title":"{notif_title}","body":"{notif_body}","url":"/queue"}}',
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@samwebdevs.dpdns.org"}
            )
            success_count += 1
            success_by_tenant[user_tenant_id] += 1
            
            if detailed_logging and user:
                db.add(EventLog(
                    event_type="PUSH_SENT_DEVICE",
                    severity="info",
                    payload={"tenant_id": user_tenant_id, "user_id": user.id, "endpoint": sub.endpoint[:30], "status": "success", "title": notif_title}
                ))
        except Exception as e:
            failure_by_tenant[user_tenant_id] += 1
            logger.error(f"Failed to push booking notification to {sub.endpoint[:30]}... Error: {str(e)}")
            if detailed_logging and user:
                db.add(EventLog(
                    event_type="PUSH_SENT_DEVICE",
                    severity="error",
                    payload={"tenant_id": user_tenant_id, "user_id": user.id, "endpoint": sub.endpoint[:30], "status": "failed", "error": str(e), "title": notif_title}
                ))
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in [404, 410]:
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
                payload={"tenant_id": t_id, "success_count": sc, "failure_count": fc, "title": full_title}
            ))
            
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit booking push logs: {e}")
        db.rollback()
        
    return success_count
