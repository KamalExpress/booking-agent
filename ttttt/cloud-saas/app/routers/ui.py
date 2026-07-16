from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import os
from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount, SystemSetting, User, Tenant, PushSubscription, AuditLog
from models import SessionLocal
from secrets_manager import secrets_manager
from auth import get_current_user, require_tenant_admin, get_current_user_from_cookie, RoleEnum, get_password_hash
from fastapi import HTTPException

def get_ui_user(request: Request, db: Session):
    try:
        return get_current_user_from_cookie(request, db)
    except HTTPException:
        return None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(tags=["UI"])

# Build absolute path to templates directory to avoid Docker WORKDIR issues
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request}
    )

@router.get("/", response_class=HTMLResponse)
async def overview_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(seconds=WorkerNode.WORKER_TIMEOUT_SECONDS)
    
    # Active workers are those not banned/disabled AND have sent a heartbeat in the last 60s
    active_workers = db.query(WorkerNode).filter(
        WorkerNode.status == 'Active',
        WorkerNode.last_heartbeat >= cutoff
    ).count()
    
    active_assignments = db.query(Assignment).filter(Assignment.status == 'Leased').count()
    
    # Slots found in last 24h
    yesterday = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    slots_found = db.query(EventLog).filter(
        EventLog.event_type == 'SLOT_FOUND',
        EventLog.created_at >= yesterday
    ).count()

    recent_logs = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(10).all()
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "user": user,
            "active_page": "overview",
            "active_workers": active_workers,
            "active_assignments": active_assignments,
            "slots_found": slots_found,
            "recent_logs": recent_logs
        }
    )

@router.get("/workers", response_class=HTMLResponse)
async def workers_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    workers = db.query(WorkerNode).order_by(WorkerNode.last_heartbeat.desc()).all()
            
    return templates.TemplateResponse(
        request=request,
        name="workers.html",
        context={
            "request": request,
            "user": user,
            "active_page": "workers",
            "workers": workers
        }
    )

@router.get("/workers/{worker_id}", response_class=HTMLResponse)
async def worker_detail_page(worker_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    worker = db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
    if not worker:
        return RedirectResponse(url="/workers")
        
    leases = db.query(Lease).filter(Lease.worker_id == worker_id).all()
    logs = db.query(EventLog).filter(EventLog.worker_id == worker_id).order_by(EventLog.created_at.desc()).limit(100).all()
    
    import os
    terminal_logs = ""
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "worker_logs")
    log_file = os.path.join(logs_dir, f"{worker_id}.log")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            terminal_logs = "".join(lines[-500:]) # Keep last 500 lines for UI
            
    return templates.TemplateResponse(
        request=request,
        name="worker_detail.html",
        context={
            "request": request,
            "user": user,
            "active_page": "workers",
            "worker": worker,
            "leases": leases,
            "logs": logs,
            "terminal_logs": terminal_logs
        }
    )

@router.get("/workers/{worker_id}/logs/download")
async def download_worker_logs(worker_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    import os
    from fastapi.responses import FileResponse
    log_file = os.path.join(os.path.dirname(__file__), "..", "..", "worker_logs", f"{worker_id}.log")
    if not os.path.exists(log_file):
        return RedirectResponse(url=f"/workers/{worker_id}", status_code=303)
    return FileResponse(path=log_file, filename=f"worker_{worker_id}.log", media_type="text/plain")

@router.post("/workers/{worker_id}/logs/clear")
async def clear_worker_logs(worker_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    import os
    log_file = os.path.join(os.path.dirname(__file__), "..", "..", "worker_logs", f"{worker_id}.log")
    if os.path.exists(log_file):
        open(log_file, 'w').close()
    return RedirectResponse(url=f"/workers/{worker_id}", status_code=303)

@router.post("/workers/{worker_id}/action")
async def worker_action(worker_id: str, request: Request, action: str = Form(...), db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    worker = db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
    if worker:
        if action == "accept_jobs":
            worker.scheduling_state = "Accepting Jobs"
        elif action == "stop_accepting":
            worker.scheduling_state = "Stop Accepting Jobs"
        elif action == "drain":
            worker.scheduling_state = "Draining"
        elif action == "disable":
            worker.scheduling_state = "Disabled"
        elif action == "maintenance":
            worker.scheduling_state = "Maintenance"
        db.commit()
    return RedirectResponse(url=f"/workers/{worker_id}", status_code=303)

@router.get("/assignments", response_class=HTMLResponse)
async def assignments_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    assignments = db.query(Assignment).order_by(Assignment.id.desc()).all()
    
    # Attach scraper account info and current lease
    for asm in assignments:
        acc = db.query(ScraperAccount).filter(ScraperAccount.id == asm.scraper_account_id).first()
        asm.account_username = acc.username if acc else "Unknown"
        
        lease = db.query(Lease).filter(Lease.assignment_id == asm.id).first()
        asm.leased_to_worker = lease.worker_id if lease else None
        
    accounts = db.query(ScraperAccount).all()
    return templates.TemplateResponse(
        request=request,
        name="assignments.html",
        context={
            "request": request,
            "user": user,
            "active_page": "assignments",
            "assignments": assignments,
            "accounts": accounts
        }
    )

@router.post("/assignments/create")
async def create_assignment(
    request: Request,
    scraper_account_id: int = Form(...),
    target_start_date: str = Form(...),
    target_end_date: str = Form(...),
    visa_center: str = Form(...),
    required_labels: str = Form(""),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)

    import json
    try:
        start_date = datetime.strptime(target_start_date, '%Y-%m-%d')
        end_date = datetime.strptime(target_end_date, '%Y-%m-%d')
        
        parsed_labels = {}
        if required_labels:
            try:
                parsed_labels = json.loads(required_labels)
            except json.JSONDecodeError:
                pass
                
        new_assignment = Assignment(
            scraper_account_id=scraper_account_id,
            date_from=start_date.strftime('%d/%m/%Y'),
            date_to=end_date.strftime('%d/%m/%Y'),
            visa_center=visa_center,
            required_labels=parsed_labels,
            status='Active'
        )
        db.add(new_assignment)
        db.commit()
    except Exception as e:
        print(f"Failed to create assignment: {e}")
        db.rollback()

@router.post("/workers/{worker_id}/edit")
async def edit_worker(worker_id: str, request: Request, labels: str = Form(""), max_concurrency: int = Form(1), db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    import json
    worker = db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
    if worker:
        try:
            parsed_labels = json.loads(labels) if labels else {}
            worker.labels = parsed_labels
            worker.max_concurrency = max_concurrency
            db.commit()
        except Exception as e:
            print(f"Failed to update worker: {e}")
            db.rollback()
    return RedirectResponse(url=f"/workers/{worker_id}", status_code=303)
        
    return RedirectResponse(url="/assignments", status_code=303)

@router.get("/assignments/{assignment_id}", response_class=HTMLResponse)
async def assignment_detail_page(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        return RedirectResponse(url="/assignments")
        
    account = db.query(ScraperAccount).filter(ScraperAccount.id == assignment.scraper_account_id).first()
    logs = db.query(EventLog).filter(EventLog.assignment_id == assignment_id).order_by(EventLog.created_at.desc()).limit(50).all()
    
    return templates.TemplateResponse(
        request=request,
        name="assignment_detail.html",
        context={
            "request": request,
            "user": user,
            "active_page": "assignments",
            "assignment": assignment,
            "account": account,
            "logs": logs
        }
    )

@router.post("/assignments/{assignment_id}/status")
async def update_assignment_status(
    assignment_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment:
        if status in ["Active", "Paused", "Completed", "Cancelled"]:
            assignment.status = status
            db.commit()
            
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.post("/assignments/{assignment_id}/edit")
async def edit_assignment(
    assignment_id: int,
    request: Request,
    visa_center: str = Form(...),
    date_from: str = Form(...),
    date_to: str = Form(...),
    polling_interval: int = Form(...),
    priority: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment:
        assignment.visa_center = visa_center
        assignment.date_from = date_from
        assignment.date_to = date_to
        assignment.polling_interval = polling_interval
        assignment.priority = priority
        db.commit()
            
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    accounts = db.query(ScraperAccount).order_by(ScraperAccount.id.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "request": request,
            "user": user,
            "active_page": "accounts",
            "accounts": accounts
        }
    )

@router.post("/accounts/create")
async def create_account(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    proxy_string: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    new_account = ScraperAccount(
        username=username,
        password=password,
        proxy_string=proxy_string,
        status='Idle'
    )
    db.add(new_account)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=303)

@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail_page(account_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    account = db.query(ScraperAccount).filter(ScraperAccount.id == account_id).first()
    if not account:
        return RedirectResponse(url="/accounts")
        
    assignments = db.query(Assignment).filter(Assignment.scraper_account_id == account_id).all()
    
    return templates.TemplateResponse(
        request=request,
        name="account_detail.html",
        context={
            "request": request,
            "user": user,
            "active_page": "accounts",
            "account": account,
            "assignments": assignments
        }
    )

@router.post("/accounts/{account_id}/edit")
async def edit_account(
    account_id: int,
    username: str = Form(...),
    password: str = Form(...),
    proxy_string: str = Form(None),
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    account = db.query(ScraperAccount).filter(ScraperAccount.id == account_id).first()
    if account:
        account.username = username
        account.password = password
        account.proxy_string = proxy_string
        account.status = status
        db.commit()
            
    return RedirectResponse(url=f"/accounts/{account_id}", status_code=303)

@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    logs = db.query(EventLog).order_by(EventLog.id.desc()).limit(100).all()
    
    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={
            "request": request,
            "user": user,
            "active_page": "logs",
            "logs": logs
        }
    )

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    settings_db = db.query(SystemSetting).all()
    settings_dict = {s.key: s for s in settings_db}
    
    # Check if captcha API key is configured
    captcha_configured = "captcha.api_key" in settings_dict and settings_dict["captcha.api_key"].encrypted_value
    
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "request": request,
            "user": user,
            "active_page": "settings",
            "settings": settings_dict,
            "captcha_configured": captcha_configured
        }
    )

@router.post("/settings/captcha")
async def update_captcha_settings(
    request: Request,
    provider: str = Form(...),
    api_key: str = Form(""),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    # Update Provider (Plaintext)
    prov_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.provider").first()
    if not prov_setting:
        prov_setting = SystemSetting(key="captcha.provider", updated_by="admin")
        db.add(prov_setting)
    prov_setting.value = provider
    
    # Update API Key (Encrypted) if provided
    if api_key.strip():
        key_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.api_key").first()
        if not key_setting:
            key_setting = SystemSetting(key="captcha.api_key", updated_by="admin")
            db.add(key_setting)
        key_setting.encrypted_value = secrets_manager.encrypt(api_key.strip())
        
    # Bump runtime config version to force workers to refresh
    version_setting = db.query(SystemSetting).filter(SystemSetting.key == "runtime.config.version").first()
    if not version_setting:
        version_setting = SystemSetting(key="runtime.config.version", value="1", updated_by="admin")
        db.add(version_setting)
    else:
        version_setting.value = str(int(version_setting.value) + 1)
        
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/settings/global")
async def update_global_settings(
    request: Request,
    default_polling_interval: str = Form("300"),
    default_date_from: str = Form(""),
    default_date_to: str = Form(""),
    notify_login_success: str = Form(None),
    notify_slots_found: str = Form(None),
    notify_no_slots_found: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    settings_to_update = {
        "global.default_polling_interval": default_polling_interval,
        "global.default_date_from": default_date_from,
        "global.default_date_to": default_date_to,
        "notify.login_success": "true" if notify_login_success else "false",
        "notify.slots_found": "true" if notify_slots_found else "false",
        "notify.no_slots_found": "true" if notify_no_slots_found else "false",
    }
    
    for key, value in settings_to_update.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not setting:
            setting = SystemSetting(key=key, updated_by="admin")
            db.add(setting)
        setting.value = value
        
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    from models import PushSubscription
    subs = db.query(PushSubscription).all()
    return templates.TemplateResponse(
        request=request,
        name="diagnostics.html",
        context={"request": request, "user": user, "active_tab": "diagnostics", "subs": subs}
    )

@router.get("/manifest.json")
async def get_manifest():
    return FileResponse(os.path.join(BASE_DIR, "..", "static", "manifest.json"))

@router.get("/sw.js")
async def get_sw():
    return FileResponse(os.path.join(BASE_DIR, "..", "static", "sw.js"))

@router.get("/icon-192.png")
async def get_icon192():
    return FileResponse(os.path.join(BASE_DIR, "..", "static", "icon-192.png"))

@router.get("/icon-512.png")
async def get_icon512():
    return FileResponse(os.path.join(BASE_DIR, "..", "static", "icon-512.png"))

@router.post("/api/diagnostics/test-captcha")
async def test_captcha_api(current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    import requests
    captcha_api_key_setting = db.query(SystemSetting).filter(SystemSetting.key == "captcha.api_key").first()
    decrypted_api_key = ""
    if captcha_api_key_setting:
        from secrets_manager import secrets_manager
        try:
            decrypted_api_key = secrets_manager.decrypt(captcha_api_key_setting.value)
        except:
            pass

    if not decrypted_api_key:
        return {"status": "error", "detail": "CapSolver API Key not configured"}

    try:
        res = requests.post("https://api.capsolver.com/getBalance", json={"clientKey": decrypted_api_key}, timeout=10)
        data = res.json()
        if data.get("errorId") == 0:
            return {"status": "ok", "balance": data.get("balance", 0)}
        else:
            return {"status": "error", "detail": data.get("errorDescription", "Unknown Error")}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.post("/api/diagnostics/simulate-event")
async def simulate_event(event_type: str = Form(...), current_user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    from notifications import send_push_notification
    from datetime import datetime
    
    if event_type == "NO_SLOTS_FOUND":
        friendly_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        send_push_notification(db, "Slot Monitor", f"No Slots available; last checked: {friendly_time}")
        
    elif event_type == "SLOT_FOUND":
        send_push_notification(db, "Slots Found!", "Slots are available; you can try booking now!")
        
        active_assignments = db.query(Assignment).filter(Assignment.status.in_(["Active", "Leased"])).all()
        for asm in active_assignments:
            asm.status = "Paused"
            
        if active_assignments:
            assignment_ids = [a.id for a in active_assignments]
            db.query(Lease).filter(Lease.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)
            
        db.commit()
        
    return RedirectResponse(url="/diagnostics", status_code=303)


@router.get("/tenants", response_class=HTMLResponse)
async def tenants_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    tenants = db.query(Tenant).order_by(Tenant.id.desc()).all()
    # also fetch the first admin user for each tenant to show their email
    for t in tenants:
        t.admin_email = next((u.email for u in t.users if u.role == RoleEnum.TENANT_ADMIN), "-")
        
    return templates.TemplateResponse(
        request=request,
        name="tenants.html",
        context={
            "request": request,
            "user": user,
            "active_page": "tenants",
            "tenants": tenants
        }
    )

@router.post("/tenants/create")
async def create_tenant(
    request: Request,
    tenant_name: str = Form(...),
    admin_email: str = Form(...),
    admin_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    # Check if tenant or user exists
    existing_tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
    existing_user = db.query(User).filter(User.email == admin_email).first()
    
    if not existing_tenant and not existing_user:
        new_tenant = Tenant(name=tenant_name)
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)
        
        new_user = User(
            tenant_id=new_tenant.id,
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            role=RoleEnum.TENANT_ADMIN
        )
        db.add(new_user)
        db.commit()
        
    return RedirectResponse(url="/tenants", status_code=303)

@router.post("/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: int,
    request: Request,
    status: str = Form(...), # "active" or "suspended"
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        # Prevent suspension of the Default Tenant
        if tenant.id == 1 and status != "active":
            return RedirectResponse(url="/tenants", status_code=303)
            
        tenant.is_active = (status == "active")
        # Update active state for all users under tenant
        for u in tenant.users:
            u.is_active = tenant.is_active
        db.commit()
        
    return RedirectResponse(url="/tenants", status_code=303)


@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def tenant_detail_page(tenant_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return RedirectResponse(url="/tenants", status_code=303)
        
    staff = db.query(User).filter(User.tenant_id == tenant_id).all()
    staff_ids = [s.id for s in staff]
    
    push_subs_count = 0
    if staff_ids:
        push_subs_count = db.query(PushSubscription).filter(PushSubscription.user_id.in_(staff_ids)).count()
        
    audit_events_count = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).count()
    
    return templates.TemplateResponse(
        request=request,
        name="tenant_detail.html",
        context={
            "request": request,
            "user": user,
            "active_page": "tenants",
            "tenant": tenant,
            "staff": staff,
            "metrics": {
                "total_staff": len(staff),
                "active_devices": push_subs_count,
                "audit_events": audit_events_count
            }
        }
    )

@router.post("/users/{user_id}/edit")
async def edit_user(
    user_id: int,
    request: Request,
    email: str = Form(...),
    full_name: str = Form(None),
    role: str = Form(...),
    password: str = Form(None),
    db: Session = Depends(get_db)
):
    current_user = get_ui_user(request, db)
    if not current_user or current_user.role not in [RoleEnum.SUPER_ADMIN, RoleEnum.TENANT_ADMIN]:
        return RedirectResponse(url="/", status_code=303)
        
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        return RedirectResponse(url="/", status_code=303)
        
    # Tenant Admins can only edit users within their own tenant
    if current_user.role == RoleEnum.TENANT_ADMIN and target_user.tenant_id != current_user.tenant_id:
        return RedirectResponse(url="/", status_code=303)
        
    target_user.email = email
    target_user.full_name = full_name
    try:
        new_role = RoleEnum(role)
        # Prevent self-demotion for SUPER_ADMIN
        if target_user.id == current_user.id and target_user.role == RoleEnum.SUPER_ADMIN and new_role != RoleEnum.SUPER_ADMIN:
            pass # Ignore the demotion attempt
        # Prevent TENANT_ADMIN from creating a SUPER_ADMIN
        elif current_user.role == RoleEnum.TENANT_ADMIN and new_role == RoleEnum.SUPER_ADMIN:
            pass # Ignore the upgrade attempt
        else:
            target_user.role = new_role
    except ValueError:
        pass # Handle invalid role gracefully
    
    if password and password.strip():
        target_user.hashed_password = get_password_hash(password.strip())
        
    db.commit()
    
    if current_user.role == RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url=f"/tenants/{target_user.tenant_id}", status_code=303)
    return RedirectResponse(url="/staff", status_code=303)

@router.post("/users/create")
async def create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(None),
    role: str = Form(...),
    password: str = Form(...),
    tenant_id: int = Form(None),
    db: Session = Depends(get_db)
):
    current_user = get_ui_user(request, db)
    if not current_user or current_user.role not in [RoleEnum.SUPER_ADMIN, RoleEnum.TENANT_ADMIN]:
        return RedirectResponse(url="/", status_code=303)
        
    # Validation & Context Switching
    if current_user.role == RoleEnum.TENANT_ADMIN:
        # Force the tenant ID to the admin's tenant ID
        assigned_tenant_id = current_user.tenant_id
        # Prevent TENANT_ADMIN from creating a SUPER_ADMIN
        try:
            assigned_role = RoleEnum(role)
        except ValueError:
            assigned_role = RoleEnum.STAFF
            
        if assigned_role == RoleEnum.SUPER_ADMIN:
            assigned_role = RoleEnum.STAFF # Fallback
    else:
        # SUPER_ADMIN must provide a valid tenant_id
        if not tenant_id:
            return RedirectResponse(url="/tenants", status_code=303)
        assigned_tenant_id = tenant_id
        try:
            assigned_role = RoleEnum(role)
        except ValueError:
            assigned_role = RoleEnum.STAFF
        
    # Check if email exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if current_user.role == RoleEnum.SUPER_ADMIN:
            return RedirectResponse(url=f"/tenants/{assigned_tenant_id}", status_code=303)
        return RedirectResponse(url="/staff", status_code=303)
        
    new_user = User(
        tenant_id=assigned_tenant_id,
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role=assigned_role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    
    if current_user.role == RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url=f"/tenants/{assigned_tenant_id}", status_code=303)
    return RedirectResponse(url="/staff", status_code=303)

@router.get("/staff", response_class=HTMLResponse)
async def staff_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role not in [RoleEnum.TENANT_ADMIN, RoleEnum.SUPER_ADMIN]:
        return RedirectResponse(url="/", status_code=303)
        
    staff = db.query(User).filter(User.tenant_id == user.tenant_id).all()
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    
    return templates.TemplateResponse(
        request=request,
        name="staff.html",
        context={
            "request": request,
            "user": user,
            "active_page": "staff",
            "staff": staff,
            "tenant": tenant
        }
    )

@router.get("/directory", response_class=HTMLResponse)
async def directory_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    users = db.query(User).order_by(User.id.desc()).all()
    push_devices = db.query(PushSubscription).order_by(PushSubscription.created_at.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="directory.html",
        context={
            "request": request,
            "user": user,
            "active_page": "directory",
            "users": users,
            "push_devices": push_devices
        }
    )
