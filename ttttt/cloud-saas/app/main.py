from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from cryptography.fernet import Fernet
import tempfile

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import SessionLocal, engine, Base, User, Tenant, RoleEnum, AuditLog, MonitorConfig, PushSubscription, ScraperAccount
from auth import get_current_user, require_super_admin, require_tenant_admin, create_access_token, verify_password, get_password_hash
# VAPID setup moved to notifications.py

app = FastAPI(title="Kamal Express SaaS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# No Global Monitor Thread in the new architecture
from core.state import global_captcha_state, cloud_log_handler
import logging

# Attach cloud log handler to the root logger
logging.getLogger().addHandler(cloud_log_handler)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

from routers.worker import router as worker_router
from routers.ui import router as ui_router

app.include_router(worker_router)
app.include_router(ui_router)

@app.on_event("startup")
def startup_event():
    # Auto-seed the database if it's empty
    from init_db import init_db
    init_db()

@app.on_event("shutdown")
def shutdown_event():
    pass

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_audit(db: Session, user: User, action: str):
    log = AuditLog(user_id=user.id, tenant_id=user.tenant_id, action=action)
    db.add(log)
    db.commit()

# --- Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    can_solve_captcha: bool = False

class PushSubRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str

class UserCreate(BaseModel):
    email: str
    password: str
    role: RoleEnum
    can_solve_captcha: bool = False

class ConfigUpdate(BaseModel):
    date_from: str
    date_to: str
    holidays: str
    interval_minutes: int
    captcha_strategy: str
    captcha_api_key: str = None
    is_active: bool
    is_demo: bool = False

class TenantCreate(BaseModel):
    name: str
    admin_email: str
    admin_password: str

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[RoleEnum] = None
    can_solve_captcha: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    tenant_id: int
    can_solve_captcha: bool

class ScraperAccountCreate(BaseModel):
    username: str
    password: str
    is_active: bool = True

class ScraperAccountUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class ScraperAccountResponse(BaseModel):
    id: int
    username: str
    is_active: bool

# --- Routes ---
@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
        
    log_audit(db, user, "Logged in")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "can_solve_captcha": user.can_solve_captcha}

@app.get("/api/users/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role, "tenant_id": current_user.tenant_id, "can_solve_captcha": current_user.can_solve_captcha}

@app.get("/api/users")
def get_users(current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    if current_user.role == RoleEnum.SUPER_ADMIN:
        users = db.query(User).all()
    else:
        users = db.query(User).filter(User.tenant_id == current_user.tenant_id).all()
    return [{"id": u.id, "email": u.email, "role": u.role, "tenant_id": u.tenant_id, "can_solve_captcha": u.can_solve_captcha} for u in users]

@app.post("/api/users")
def create_user(req: UserCreate, current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    if req.role == RoleEnum.SUPER_ADMIN and current_user.role != RoleEnum.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot create Super Admin")
        
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    new_user = User(
        tenant_id=current_user.tenant_id,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        role=req.role,
        can_solve_captcha=req.can_solve_captcha
    )
    db.add(new_user)
    db.commit()
    log_audit(db, current_user, f"Created user {req.email}")
    return {"status": "success"}

@app.put("/api/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.role != RoleEnum.SUPER_ADMIN and target.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot edit users outside your tenant")
        
    if target.role == RoleEnum.SUPER_ADMIN and current_user.role != RoleEnum.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot edit Super Admin")

    if req.email and req.email != target.email:
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        target.email = req.email
        
    if req.password:
        target.hashed_password = get_password_hash(req.password)
        
    if req.role and current_user.role == RoleEnum.SUPER_ADMIN:
        target.role = req.role

    if req.can_solve_captcha is not None:
        target.can_solve_captcha = req.can_solve_captcha

    db.commit()
    log_audit(db, current_user, f"Updated user {user_id}")
    return {"status": "success"}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.role != RoleEnum.SUPER_ADMIN and target.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot delete users outside your tenant")
        
    db.delete(target)
    db.commit()
    log_audit(db, current_user, f"Deleted user {user_id}")
    return {"status": "success"}

@app.get("/api/tenants")
def get_tenants(current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    tenants = db.query(Tenant).all()
    result = []
    for t in tenants:
        admin_user = db.query(User).filter(User.tenant_id == t.id, User.role.in_([RoleEnum.TENANT_ADMIN, RoleEnum.SUPER_ADMIN])).first()
        admin_email = admin_user.email if admin_user else "N/A"
        result.append({
            "id": t.id, 
            "name": t.name, 
            "admin_email": admin_email,
            "is_active": t.is_active, 
            "created_at": t.created_at
        })
    return result

@app.post("/api/tenants")
def create_tenant(req: TenantCreate, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")
        
    existing_user = db.query(User).filter(User.email == req.admin_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Admin email already registered")
        
    new_tenant = Tenant(name=req.name)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    
    admin_user = User(
        tenant_id=new_tenant.id,
        email=req.admin_email,
        hashed_password=get_password_hash(req.admin_password),
        role=RoleEnum.TENANT_ADMIN
    )
    db.add(admin_user)
    db.commit()
    log_audit(db, current_user, f"Created tenant {req.name}")
    return {"status": "success"}

@app.put("/api/tenants/{tenant_id}")
def update_tenant(tenant_id: int, req: TenantUpdate, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    target = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    if req.name and req.name != target.name:
        existing = db.query(Tenant).filter(Tenant.name == req.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tenant name already exists")
        target.name = req.name
        
    admin_user = db.query(User).filter(User.tenant_id == tenant_id, User.role == RoleEnum.TENANT_ADMIN).first()
    if admin_user:
        if req.admin_email and req.admin_email != admin_user.email:
            existing_user = db.query(User).filter(User.email == req.admin_email).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="Admin email already registered")
            admin_user.email = req.admin_email
            
        if req.admin_password:
            admin_user.hashed_password = get_password_hash(req.admin_password)
            
    db.commit()
    log_audit(db, current_user, f"Updated tenant {tenant_id}")
    return {"status": "success"}

@app.delete("/api/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    target = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if target.id == 1:
        raise HTTPException(status_code=403, detail="Cannot delete the root tenant")
        
    db.delete(target)
    db.commit()
    log_audit(db, current_user, f"Deleted tenant {tenant_id}")
    return {"status": "success"}

@app.put("/api/tenants/{tenant_id}/status")
def toggle_tenant_status(tenant_id: int, req: dict, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    if tenant_id == 1:
        raise HTTPException(status_code=403, detail="Cannot modify the root tenant")
    
    target = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    new_status = req.get("is_active", False)
    target.is_active = new_status
    
    # Cascade to all users under this tenant
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    for u in users:
        u.is_active = new_status
        
    db.commit()
    log_audit(db, current_user, f"Set tenant {tenant_id} active status to {new_status}")
    return {"status": "success"}

@app.get("/api/monitor/config")
def get_config(current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    config = db.query(MonitorConfig).first()
    return config

@app.post("/api/monitor/config")
def update_config(req: ConfigUpdate, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    config = db.query(MonitorConfig).first()
    if not config:
        config = MonitorConfig()
        db.add(config)
        
    config.date_from = req.date_from
    config.date_to = req.date_to
    config.holidays = req.holidays
    config.interval_minutes = req.interval_minutes
    config.captcha_strategy = req.captcha_strategy
    config.captcha_api_key = req.captcha_api_key
    config.is_active = req.is_active
    config.is_demo = req.is_demo
    db.commit()
    log_audit(db, current_user, f"Updated monitor config")
    return {"status": "success"}

# --- Scraper Accounts (Super Admin) ---
@app.get("/api/scraper-accounts", response_model=List[ScraperAccountResponse])
def get_scraper_accounts(current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    accounts = db.query(ScraperAccount).all()
    return [{"id": a.id, "username": a.username, "is_active": a.is_active} for a in accounts]

@app.post("/api/scraper-accounts")
def create_scraper_account(req: ScraperAccountCreate, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    existing = db.query(ScraperAccount).filter(ScraperAccount.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Account username already exists")
    new_account = ScraperAccount(username=req.username, password=req.password, is_active=req.is_active)
    db.add(new_account)
    db.commit()
    return {"status": "success"}

@app.put("/api/scraper-accounts/{account_id}")
def update_scraper_account(account_id: int, req: ScraperAccountUpdate, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    account = db.query(ScraperAccount).filter(ScraperAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if req.username is not None:
        account.username = req.username
    if req.password is not None:
        account.password = req.password
    if req.is_active is not None:
        account.is_active = req.is_active
    db.commit()
    return {"status": "success"}

@app.delete("/api/scraper-accounts/{account_id}")
def delete_scraper_account(account_id: int, current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    account = db.query(ScraperAccount).filter(ScraperAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"status": "success"}

# --- Push Subscriptions ---
@app.post("/api/monitor/quick-toggle")
def toggle_config_state(current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    config = db.query(MonitorConfig).first()
    if not config:
        config = MonitorConfig(is_active=False)
        db.add(config)
    
    config.is_active = not config.is_active
    db.commit()
    
    global monitor_thread
    if monitor_thread and config.is_active:
        monitor_thread._wake_event.set()
        
    status_str = "RESUMED" if config.is_active else "PAUSED"
    log_audit(db, current_user, f"Quick Toggled bot state to {status_str}")
    logger.info(f"*** BOT {status_str} BY USER ***")
    
    return {"status": "success", "is_active": config.is_active}

@app.get("/api/monitor/logs")
def get_monitor_logs(limit: Optional[int] = 200, current_user: User = Depends(require_tenant_admin)):
    logs = list(cloud_log_handler.log_queue)
    if limit and limit > 0:
        return logs[-limit:]
    return logs

@app.delete("/api/monitor/logs")
def clear_monitor_logs(current_user: User = Depends(require_tenant_admin)):
    cloud_log_handler.log_queue.clear()
    return {"status": "success"}

@app.post("/api/monitor/trigger")
def trigger_bot(current_user: User = Depends(require_tenant_admin)):
    global monitor_thread
    if monitor_thread:
        monitor_thread._wake_event.set()
        log_audit(next(get_db()), current_user, "Manually triggered bot run")
        return {"status": "success", "detail": "Bot signaled to run immediately"}
    return {"status": "error", "detail": "Monitor thread not running"}

@app.get("/api/captcha/pending")
def check_pending_captcha(current_user: User = Depends(get_current_user)):
    with global_captcha_state.lock:
        if global_captcha_state.is_pending:
            return {
                "pending": True,
                "sitekey": global_captcha_state.sitekey,
                "url": global_captcha_state.url
            }
        return {"pending": False}

class CaptchaSubmitRequest(BaseModel):
    token: str

@app.post("/api/captcha/submit")
def submit_captcha(req: CaptchaSubmitRequest, current_user: User = Depends(get_current_user)):
    with global_captcha_state.lock:
        if not global_captcha_state.is_pending:
            raise HTTPException(status_code=400, detail="No captcha is currently pending.")
    
    global_captcha_state.submit_token(req.token)
    return {"status": "success"}

@app.get("/api/push/vapid-public-key")
def get_vapid_public_key():
    from notifications import VAPID_PUBLIC_KEY
    return {"public_key": VAPID_PUBLIC_KEY}

@app.post("/api/push/subscribe")
def subscribe_push(req: PushSubRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == req.endpoint).first()
    if not existing:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=req.endpoint,
            p256dh=req.p256dh,
            auth=req.auth
        )
        db.add(sub)
        db.commit()
    return {"status": "success"}

@app.delete("/api/push/unsubscribe")
def unsubscribe_push(req: PushSubRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == req.endpoint).first()
    if sub:
        db.delete(sub)
    db.commit()
    return {"status": "success"}

@app.get("/api/admin/debug")
def get_system_debug(current_user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Dumps all database core entities for Super Admin debugging."""
    tenants = db.query(Tenant).all()
    users = db.query(User).all()
    subs = db.query(PushSubscription).all()
    
    return {
        "tenants": [{"id": t.id, "name": t.name} for t in tenants],
        "users": [{"id": u.id, "email": u.email, "tenant_id": u.tenant_id, "role": u.role} for u in users],
        "push_subscriptions": [{"id": s.id, "user_id": s.user_id, "endpoint": s.endpoint[:40] + "..."} for s in subs]
    }

class BroadcastRequest(BaseModel):
    message: str

@app.post("/api/push/broadcast")
def broadcast_push_alert(req: BroadcastRequest, current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    from notifications import send_push_notification
    # Get all users for this tenant
    users = db.query(User).filter(User.tenant_id == current_user.tenant_id).all()
    user_ids = [u.id for u in users]
    
    success_count = send_push_notification(db, "Admin Broadcast!", req.message, user_ids)
    
    return {"status": "ok", "delivered": success_count}

@app.post("/api/push/test")
def test_push_alert(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from notifications import send_push_notification
    success_count = send_push_notification(db, "Test Push Notification", "This is a test notification from the SaaS dashboard.", [current_user.id])
    return {"status": "ok", "delivered": success_count}

# Mount Static Files (PWA)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
