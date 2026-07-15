from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import os
from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount, SystemSetting, User
from models import SessionLocal
from secrets_manager import secrets_manager
from auth import get_current_user, require_tenant_admin

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

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "active_page": "overview",
            "active_workers": active_workers,
            "active_assignments": active_assignments,
            "slots_found": slots_found
        }
    )

@router.get("/workers", response_class=HTMLResponse)
async def workers_page(request: Request, db: Session = Depends(get_db)):
    workers = db.query(WorkerNode).order_by(WorkerNode.last_heartbeat.desc()).all()
            
    return templates.TemplateResponse(
        request=request,
        name="workers.html",
        context={
            "request": request,
            "active_page": "workers",
            "workers": workers
        }
    )

@router.get("/workers/{worker_id}", response_class=HTMLResponse)
async def worker_detail_page(worker_id: str, request: Request, db: Session = Depends(get_db)):
    worker = db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
    if not worker:
        return RedirectResponse(url="/workers")
        
    leases = db.query(Lease).filter(Lease.worker_id == worker_id).all()
    logs = db.query(EventLog).filter(EventLog.worker_id == worker_id).order_by(EventLog.created_at.desc()).limit(100).all()
    
    return templates.TemplateResponse(
        request=request,
        name="worker_detail.html",
        context={
            "request": request,
            "active_page": "workers",
            "worker": worker,
            "leases": leases,
            "logs": logs
        }
    )

@router.post("/workers/{worker_id}/action")
async def worker_action(worker_id: str, action: str = Form(...), db: Session = Depends(get_db)):
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
            "active_page": "assignments",
            "assignments": assignments,
            "accounts": accounts
        }
    )

@router.post("/assignments/create")
async def create_assignment(
    scraper_account_id: int = Form(...),
    target_start_date: str = Form(...),
    target_end_date: str = Form(...),
    visa_center: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        start_date = datetime.strptime(target_start_date, '%Y-%m-%d')
        end_date = datetime.strptime(target_end_date, '%Y-%m-%d')
        
        new_assignment = Assignment(
            scraper_account_id=scraper_account_id,
            date_from=start_date.strftime('%d/%m/%Y'),
            date_to=end_date.strftime('%d/%m/%Y'),
            visa_center=visa_center,
            status='Active'
        )
        db.add(new_assignment)
        db.commit()
    except Exception as e:
        print(f"Failed to create assignment: {e}")
        db.rollback()
        
    return RedirectResponse(url="/assignments", status_code=303)

@router.get("/assignments/{assignment_id}", response_class=HTMLResponse)
async def assignment_detail_page(assignment_id: int, request: Request, db: Session = Depends(get_db)):
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
            "active_page": "assignments",
            "assignment": assignment,
            "account": account,
            "logs": logs
        }
    )

@router.post("/assignments/{assignment_id}/status")
async def update_assignment_status(
    assignment_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment:
        if status in ["Active", "Paused", "Completed", "Cancelled"]:
            assignment.status = status
            db.commit()
            
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.post("/assignments/{assignment_id}/edit")
async def edit_assignment(
    assignment_id: int,
    visa_center: str = Form(...),
    date_from: str = Form(...),
    date_to: str = Form(...),
    polling_interval: int = Form(...),
    priority: int = Form(...),
    db: Session = Depends(get_db)
):
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
    accounts = db.query(ScraperAccount).order_by(ScraperAccount.id.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "request": request,
            "active_page": "accounts",
            "accounts": accounts
        }
    )

@router.post("/accounts/create")
async def create_account(
    username: str = Form(...),
    password: str = Form(...),
    proxy_string: str = Form(None),
    db: Session = Depends(get_db)
):
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
    account = db.query(ScraperAccount).filter(ScraperAccount.id == account_id).first()
    if not account:
        return RedirectResponse(url="/accounts")
        
    assignments = db.query(Assignment).filter(Assignment.scraper_account_id == account_id).all()
    
    return templates.TemplateResponse(
        request=request,
        name="account_detail.html",
        context={
            "request": request,
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
    logs = db.query(EventLog).order_by(EventLog.id.desc()).limit(100).all()
    
    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={
            "request": request,
            "active_page": "logs",
            "logs": logs
        }
    )

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    settings_db = db.query(SystemSetting).all()
    settings_dict = {s.key: s for s in settings_db}
    
    # Check if captcha API key is configured
    captcha_configured = "captcha.api_key" in settings_dict and settings_dict["captcha.api_key"].encrypted_value
    
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "request": request,
            "active_page": "settings",
            "settings": settings_dict,
            "captcha_configured": captcha_configured
        }
    )

@router.post("/settings/captcha")
async def update_captcha_settings(
    provider: str = Form(...),
    api_key: str = Form(""),
    db: Session = Depends(get_db)
):
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
        
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/settings/global")
async def update_global_settings(
    default_polling_interval: str = Form("300"),
    default_date_from: str = Form(""),
    default_date_to: str = Form(""),
    db: Session = Depends(get_db)
):
    settings_to_update = {
        "global.default_polling_interval": default_polling_interval,
        "global.default_date_from": default_date_from,
        "global.default_date_to": default_date_to
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
    from models import PushSubscription
    subs = db.query(PushSubscription).all()
    return templates.TemplateResponse(
        request=request,
        name="diagnostics.html",
        context={"request": request, "active_tab": "diagnostics", "subs": subs}
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
