from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import zoneinfo

import os
from models import WorkerNode, Assignment, Lease, EventLog, PortalAccount, Proxy, BookingTask, SchedulerDecision, SystemSetting, User, Tenant, PushSubscription, AuditLog, WorkerLog
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

from core.branding import get_env_branding

# Build absolute path to templates directory to avoid Docker WORKDIR issues
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def format_time_filter(dt, tz_name="Server Time", fmt='%Y-%m-%d %H:%M:%S'):
    if not dt or not isinstance(dt, datetime):
        return dt or "N/A"
    
    if not tz_name or tz_name == 'Server Time':
        return dt.strftime(fmt)
        
    try:
        # DB datetime is naive UTC based on utcnow defaults
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        target_tz = zoneinfo.ZoneInfo(tz_name)
        local_dt = dt.astimezone(target_tz)
        return local_dt.strftime(fmt)
    except Exception:
        return dt.strftime(fmt)

templates.env.filters["format_time"] = format_time_filter

def render_template(name: str, context: dict, db: Session):
    # Fetch branding settings
    brand_name = db.query(SystemSetting).filter(SystemSetting.key == "global.brand_name").first()
    brand_subtitle = db.query(SystemSetting).filter(SystemSetting.key == "global.brand_subtitle").first()
    admin_notice = db.query(SystemSetting).filter(SystemSetting.key == "global.admin_notice").first()
    
    branding = {
        "brand_name": brand_name.value if brand_name and brand_name.value else "Alamia Automation",
        "brand_subtitle": brand_subtitle.value if brand_subtitle and brand_subtitle.value else "Automating Business Solutions",
        "admin_notice": admin_notice.value if admin_notice else ""
    }
    
    context["branding"] = branding
    context["env_branding"] = get_env_branding()
    
    ui_tz = db.query(SystemSetting).filter(SystemSetting.key == "ui.timezone").first()
    context["ui_timezone"] = ui_tz.value if ui_tz and ui_tz.value else "Server Time"
    
    from services.guidance import GUIDANCE_DICT
    from services.ui_guidance import NAV_GUIDANCE_DICT
    context["guidance_dict"] = GUIDANCE_DICT
    context["nav_guidance_dict"] = NAV_GUIDANCE_DICT
    return templates.TemplateResponse(request=context["request"], name=name, context=context)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    return render_template("login.html", {"request": request}, db)

@router.get("/help", response_class=HTMLResponse)
async def playbook_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return render_template("playbook.html", {"request": request, "user": user, "active_page": "playbook"}, db)

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

    from models import SlotAvailability
    
    last_check_event = db.query(EventLog).filter(EventLog.event_type.in_(['SLOT_FOUND', 'NO_SLOTS_FOUND'])).order_by(EventLog.created_at.desc()).first()
    global_last_checked_time = last_check_event.created_at if last_check_event else None
    
    # Build status per visa center
    vc_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.visa_centers_config").first()
    vc_config_str = vc_setting.value if vc_setting and vc_setting.value else "138:26:Lahore, 137:26:Islamabad, 140:24:Doc Verification"
    
    center_statuses = []
    for center_str in vc_config_str.split(","):
        parts = center_str.strip().split(":")
        if len(parts) >= 3:
            c_id = parts[0]
            c_name = parts[2]
            
            recent_slots = db.query(SlotAvailability).filter(
                SlotAvailability.visa_center == c_id,
                SlotAvailability.created_at >= yesterday
            ).order_by(SlotAvailability.created_at.desc()).limit(10).all()
            
            user_prefs = user.preferences or {}
            muted_centers = user_prefs.get("muted_visa_centers", [])
            
            center_statuses.append({
                "id": c_id,
                "name": c_name,
                "is_open": len(recent_slots) > 0,
                "recent_slots": recent_slots,
                "last_checked_time": global_last_checked_time,
                "is_muted": c_id in muted_centers
            })
    
    recent_logs = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(15).all()
    
    # Calculate System Health
    health_score = 0
    if active_workers > 0:
        health_score += 60
        if active_workers >= 3:
            health_score += 15
            
    if global_last_checked_time:
        delta_seconds = (now - global_last_checked_time).total_seconds()
        if delta_seconds < 120:
            health_score += 25
        elif delta_seconds < 300:
            health_score += 10
            
    # Cap at 100
    health_score = min(100, health_score)
    is_healthy = health_score > 70
    
    # Fetch PWA Config
    pwa_settings = {
        "show_health_indicator": True,
        "health_indicator_mode": "percentage",
        "show_live_timeline": True,
        "show_notification_status": True
    }
    
    # Override with db settings
    pwa_db_settings = db.query(SystemSetting).filter(SystemSetting.key.like("pwa.%")).all()
    for s in pwa_db_settings:
        if s.key == "pwa.show_health_indicator":
            pwa_settings["show_health_indicator"] = s.value == "true"
        elif s.key == "pwa.health_indicator_mode":
            pwa_settings["health_indicator_mode"] = s.value
        elif s.key == "pwa.show_live_timeline":
            pwa_settings["show_live_timeline"] = s.value == "true"
        elif s.key == "pwa.show_notification_status":
            pwa_settings["show_notification_status"] = s.value == "true"
    
    # Calculate monthly push count
    from sqlalchemy import extract
    current_month = datetime.now(timezone.utc).month
    current_year = datetime.now(timezone.utc).year
    
    push_query = db.query(EventLog).filter(
        EventLog.event_type == 'PUSH_SENT',
        extract('month', EventLog.created_at) == current_month,
        extract('year', EventLog.created_at) == current_year
    )
    if user.role == RoleEnum.TENANT_ADMIN:
        from sqlalchemy import cast, String
        push_query = push_query.filter(EventLog.payload['tenant_id'].astext == str(user.tenant_id))
    
    push_logs = push_query.all()
    monthly_push_count = sum(log.payload.get('success_count', 0) if log.payload else 0 for log in push_logs)
    
    return render_template("index.html", {
        "request": request,
        "user": user,
        "active_page": "overview",
        "active_workers": active_workers,
        "active_assignments": active_assignments,
        "slots_found": slots_found,
        "center_statuses": center_statuses,
        "recent_logs": recent_logs,
        "monthly_push_count": monthly_push_count,
        "global_last_checked_time": global_last_checked_time,
        "health_score": health_score,
        "is_healthy": is_healthy,
        "pwa_settings": pwa_settings
    }, db)

@router.get("/workers", response_class=HTMLResponse)
async def workers_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    workers = db.query(WorkerNode).order_by(WorkerNode.last_heartbeat.desc()).all()
            
    return render_template("workers.html", {
        "request": request,
        "user": user,
        "active_page": "workers",
        "workers": workers
    }, db)

@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    query = db.query(EventLog).filter(EventLog.event_type.in_(['PUSH_SENT', 'PUSH_SENT_DEVICE']))
    
    if user.role == RoleEnum.TENANT_ADMIN:
        # PostgreSQL JSONB querying to filter by tenant_id inside payload
        from sqlalchemy import cast, String
        query = query.filter(EventLog.payload['tenant_id'].astext == str(user.tenant_id))
    elif user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    logs = query.order_by(EventLog.created_at.desc()).limit(200).all()
            
    return render_template("notifications.html", {
        "request": request,
        "user": user,
        "active_page": "notifications",
        "logs": logs
    }, db)

@router.get("/slots", response_class=HTMLResponse)
async def slots_history_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    from models import SlotAvailability
    slots = db.query(SlotAvailability).order_by(SlotAvailability.created_at.desc()).limit(200).all()
            
    return render_template("slot_history.html", {
        "request": request,
        "user": user,
        "active_page": "slots",
        "slots": slots
    }, db)

@router.get("/slots/{slot_id}", response_class=HTMLResponse)
async def slot_detail_page(slot_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    from models import SlotAvailability
    slot = db.query(SlotAvailability).filter(SlotAvailability.id == slot_id).first()
    if not slot:
        return RedirectResponse(url="/slots")
            
    return render_template("slot_detail.html", {
        "request": request,
        "user": user,
        "active_page": "slots",
        "slot": slot
    }, db)

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
    network_logs = db.query(WorkerLog).filter(WorkerLog.worker_id == worker_id).order_by(WorkerLog.created_at.desc()).limit(50).all()
    
    import os
    terminal_logs = ""
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "worker_logs")
    log_file = os.path.join(logs_dir, f"{worker_id}.log")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            terminal_logs = "".join(lines[-500:]) # Keep last 500 lines for UI
            
    return render_template("worker_detail.html", {
        "request": request,
        "user": user,
        "active_page": "workers",
        "worker": worker,
        "leases": leases,
        "logs": logs,
        "network_logs": network_logs,
        "terminal_logs": terminal_logs
    }, db)

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

@router.get("/workers/{worker_id}/network-logs/{log_id}/download")
async def download_network_log(worker_id: str, log_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    import json
    from fastapi.responses import Response
    log = db.query(WorkerLog).filter(WorkerLog.id == log_id, WorkerLog.worker_id == worker_id).first()
    if not log:
        return RedirectResponse(url=f"/workers/{worker_id}", status_code=303)
        
    json_str = json.dumps(log.payload, indent=2)
    filename = f"worker_{worker_id}_network_log_{log.id}.json"
    return Response(
        content=json_str, 
        media_type="application/json", 
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/workers/{worker_id}/network-logs/clear")
async def clear_network_logs(worker_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    db.query(WorkerLog).filter(WorkerLog.worker_id == worker_id).delete(synchronize_session=False)
    db.commit()
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
    # attach lease status
    for asm in assignments:
        lease = db.query(Lease).filter(Lease.assignment_id == asm.id).order_by(Lease.id.desc()).first()
        asm.lease_status = lease.status if lease else "No Lease"
        asm.leased_to_worker = lease.worker_id if lease else None
        
    accounts = db.query(PortalAccount).filter(PortalAccount.supports_scraping == True).all()
    
    # Parse available centers from settings
    vc_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.visa_centers_config").first()
    vc_config_str = vc_setting.value if vc_setting and vc_setting.value else "138:26:Lahore, 137:26:Islamabad, 140:24:Doc Verification"
    available_centers = []
    for center_str in vc_config_str.split(","):
        parts = center_str.strip().split(":")
        if len(parts) >= 3:
            available_centers.append({
                "id": parts[0],
                "type": parts[1],
                "name": parts[2],
                "value": f"{parts[0]}:{parts[1]}"
            })
            
    return render_template("assignments.html", {
        "request": request,
        "user": user,
        "active_page": "assignments",
        "assignments": assignments,
        "accounts": accounts,
        "available_centers": available_centers
    }, db)

@router.post("/assignments/create")
async def create_assignment(
    request: Request,
    target_start_date: str = Form(...),
    target_end_date: str = Form(...),
    visa_center: list[str] = Form(...),
    required_labels: str = Form(""),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)

    import json
    try:
        start_date = datetime.strptime(target_start_date, '%d/%m/%Y')
        end_date = datetime.strptime(target_end_date, '%d/%m/%Y')
        
        parsed_labels = {}
        if required_labels:
            try:
                parsed_labels = json.loads(required_labels)
            except json.JSONDecodeError:
                pass
                
        # Join multiple visa centers into a comma-separated string
        vc_string = ",".join(visa_center)
        
        new_assignment = Assignment(
            date_from=start_date.strftime('%d/%m/%Y'),
            date_to=end_date.strftime('%d/%m/%Y'),
            visa_center=vc_string,
            required_labels=parsed_labels,
            status='Active'
        )
        db.add(new_assignment)
        db.commit()
    except Exception as e:
        print(f"Failed to create assignment: {e}")
        db.rollback()
        
    return RedirectResponse(url="/assignments", status_code=303)

@router.post("/assignments/{assignment_id}/reset")
async def reset_assignment(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        # Abort any active lease
        active_lease = db.query(Lease).filter(
            Lease.assignment_id == assignment_id, 
            Lease.status == "Active"
        ).first()
        
        if active_lease:
            active_lease.status = "ABORTED"
            
        # Reset the assignment
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if assignment:
            assignment.status = "Active"
            assignment.last_checked = None
            db.commit()
    except Exception as e:
        print(f"Failed to reset assignment: {e}")
        db.rollback()
        
    return RedirectResponse(url="/assignments", status_code=303)

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
        
    logs = db.query(EventLog).filter(EventLog.assignment_id == assignment_id).order_by(EventLog.created_at.desc()).limit(50).all()
    
    # Parse available centers from settings
    vc_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.visa_centers_config").first()
    vc_config_str = vc_setting.value if vc_setting and vc_setting.value else "138:26:Lahore, 137:26:Islamabad, 140:24:Doc Verification"
    available_centers = []
    for center_str in vc_config_str.split(","):
        parts = center_str.strip().split(":")
        if len(parts) >= 3:
            available_centers.append({
                "id": parts[0],
                "type": parts[1],
                "name": parts[2],
                "value": f"{parts[0]}:{parts[1]}"
            })
            
    selected_centers = [c.strip() for c in assignment.visa_center.split(",")] if assignment.visa_center else []
    
    return render_template("assignment_detail.html", {
        "request": request,
        "user": user,
        "active_page": "assignments",
        "assignment": assignment,
        "logs": logs,
        "available_centers": available_centers,
        "selected_centers": selected_centers
    }, db)

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
    visa_center: list[str] = Form(...),
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
        assignment.visa_center = ",".join(visa_center)
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
        
    accounts = db.query(PortalAccount).order_by(PortalAccount.id.desc()).all()
    
    return render_template("accounts.html", {
        "request": request,
        "user": user,
        "active_page": "accounts",
        "accounts": accounts
    }, db)

@router.post("/accounts/create")
async def create_account(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    supports_scraping: bool = Form(False),
    supports_booking: bool = Form(False),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    new_account = PortalAccount(
        username=username,
        password=password,
        supports_scraping=supports_scraping,
        supports_booking=supports_booking,
        status='READY'
    )
    db.add(new_account)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=303)

@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail_page(account_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    account = db.query(PortalAccount).filter(PortalAccount.id == account_id).first()
    if not account:
        return RedirectResponse(url="/accounts")
        
    leases = db.query(Lease).filter(Lease.portal_account_id == account_id).all()
    
    return render_template("account_detail.html", {
        "request": request,
        "user": user,
        "active_page": "accounts",
        "account": account,
        "leases": leases
    }, db)

@router.post("/accounts/{account_id}/edit")
async def edit_account(
    account_id: int,
    username: str = Form(...),
    password: str = Form(...),
    status: str = Form(...),
    supports_scraping: bool = Form(False),
    supports_booking: bool = Form(False),
    db: Session = Depends(get_db)
):
    account = db.query(PortalAccount).filter(PortalAccount.id == account_id).first()
    if account:
        account.username = username
        account.password = password
        account.supports_scraping = supports_scraping
        account.supports_booking = supports_booking
        account.status = status
        db.commit()
            
    return RedirectResponse(url=f"/accounts/{account_id}", status_code=303)

@router.get("/proxies", response_class=HTMLResponse)
async def proxies_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    proxies = db.query(Proxy).order_by(Proxy.id.desc()).all()
    
    return render_template("proxies.html", {
        "request": request,
        "user": user,
        "active_page": "proxies",
        "proxies": proxies
    }, db)

@router.post("/proxies/create")
async def create_proxies(
    request: Request,
    proxies_text: str = Form(...),
    supports_scraping: bool = Form(False),
    supports_booking: bool = Form(False),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    lines = proxies_text.strip().split("\\n")
    for line in lines:
        line = line.strip()
        if not line: continue
        parts = line.split(":")
        if len(parts) >= 2:
            p = Proxy(
                host=parts[0],
                port=parts[1],
                username=parts[2] if len(parts) > 2 else None,
                password=parts[3] if len(parts) > 3 else None,
                supports_scraping=supports_scraping,
                supports_booking=supports_booking
            )
            db.add(p)
    db.commit()
    return RedirectResponse(url="/proxies", status_code=303)

@router.post("/proxies/{proxy_id}/delete")
async def delete_proxy(proxy_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    db.query(Proxy).filter(Proxy.id == proxy_id).delete()
    db.commit()
    return RedirectResponse(url="/proxies", status_code=303)

@router.get("/booking-tasks", response_class=HTMLResponse)
async def booking_tasks_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    tasks = db.query(BookingTask).order_by(BookingTask.id.desc()).all()
    
    return render_template("booking_tasks.html", {
        "request": request,
        "user": user,
        "active_page": "booking_tasks",
        "tasks": tasks
    }, db)

@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    logs = db.query(EventLog).order_by(EventLog.id.desc()).limit(100).all()
    
    return render_template("logs.html", {
        "request": request,
        "user": user,
        "active_page": "logs",
        "logs": logs
    }, db)

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    settings_db = db.query(SystemSetting).all()
    settings_dict = {s.key: s for s in settings_db}
    
    # Check if captcha API key is configured
    captcha_configured = "captcha.api_key" in settings_dict and settings_dict["captcha.api_key"].encrypted_value
    
    return render_template("settings.html", {
        "request": request,
        "user": user,
        "active_page": "settings",
        "settings": settings_dict,
        "captcha_configured": captcha_configured
    }, db)

@router.get("/captcha", response_class=HTMLResponse)
async def captcha_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    settings_db = db.query(SystemSetting).all()
    settings_dict = {s.key: s for s in settings_db}
    
    # Check if captcha API key is configured
    captcha_configured = "captcha.api_key" in settings_dict and settings_dict["captcha.api_key"].encrypted_value
    
    return render_template("captcha.html", {
        "request": request,
        "user": user,
        "active_page": "captcha",
        "settings": settings_dict,
        "captcha_configured": captcha_configured
    }, db)

@router.post("/captcha")
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
    return RedirectResponse(url="/captcha", status_code=303)

@router.post("/settings/global")
async def update_global_settings(
    request: Request,
    default_polling_interval: str = Form("300"),
    default_date_from: str = Form(""),
    default_date_to: str = Form(""),
    min_slot_delay: str = Form("4"),
    max_slot_delay: str = Form("8"),
    brand_name: str = Form("Alamia Automation"),
    brand_subtitle: str = Form("Automating Business Solutions"),
    admin_notice: str = Form(""),
    visa_centers_config: str = Form("138:26:Lahore, 137:26:Islamabad, 140:24:Doc Verification"),
    notify_login_success: str = Form(None),
    notify_slots_found: str = Form(None),
    notify_no_slots_found: str = Form(None),
    detailed_push_logging: str = Form(None),
    ui_timezone: str = Form("Server Time"),
    pwa_show_health_indicator: str = Form(None),
    pwa_health_indicator_mode: str = Form("percentage"),
    pwa_show_live_timeline: str = Form(None),
    pwa_show_notification_status: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
    settings_to_update = {
        "global.default_polling_interval": default_polling_interval,
        "global.default_date_from": default_date_from,
        "global.default_date_to": default_date_to,
        "global.min_slot_delay": min_slot_delay,
        "global.max_slot_delay": max_slot_delay,
        "ui.timezone": ui_timezone,
        "global.brand_name": brand_name,
        "global.brand_subtitle": brand_subtitle,
        "global.admin_notice": admin_notice,
        "global.visa_centers_config": visa_centers_config,
        "notify.login_success": "true" if notify_login_success else "false",
        "notify.slots_found": "true" if notify_slots_found else "false",
        "notify.no_slots_found": "true" if notify_no_slots_found else "false",
        "global.detailed_push_logging": "true" if detailed_push_logging else "false",
        "pwa.show_health_indicator": "true" if pwa_show_health_indicator else "false",
        "pwa.health_indicator_mode": pwa_health_indicator_mode,
        "pwa.show_live_timeline": "true" if pwa_show_live_timeline else "false",
        "pwa.show_notification_status": "true" if pwa_show_notification_status else "false",
    }
    
    for key, value in settings_to_update.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not setting:
            setting = SystemSetting(key=key, updated_by="admin")
            db.add(setting)
        setting.value = value
        
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

from services.guidance import get_guidance

@router.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    from models import PushSubscription
    subs = db.query(PushSubscription).all()
    
    scheduler_decisions = db.query(SchedulerDecision).order_by(SchedulerDecision.created_at.desc()).limit(100).all()
    
    # Attach guidance to decisions
    for d in scheduler_decisions:
        d.guidance = get_guidance(d.decision_type)
        
    event_logs = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(100).all()
    for e in event_logs:
        e.guidance = get_guidance(e.event_type)
        
    return render_template("diagnostics.html", {
        "request": request,
        "user": user,
        "active_tab": "diagnostics",
        "subs": subs,
        "scheduler_decisions": scheduler_decisions,
        "event_logs": event_logs
    }, db)

@router.get("/manifest.json")
async def get_manifest(db: Session = Depends(get_db)):
    brand_name_setting = db.query(SystemSetting).filter(SystemSetting.key == "global.brand_name").first()
    db_brand_name = brand_name_setting.value if brand_name_setting and brand_name_setting.value else "Alamia Automation"
    
    env_branding = get_env_branding()
    # Override app name for manifest based on environment
    app_name = env_branding.app_name if env_branding.is_staging else db_brand_name
    short_name = env_branding.short_name if env_branding.is_staging else db_brand_name

    return {
      "id": env_branding.manifest_id,
      "name": app_name,
      "short_name": short_name,
      "start_url": "/",
      "display": "standalone",
      "background_color": "#111827",
      "theme_color": env_branding.theme_color,
      "icons": [
        {
          "src": "/icon-192.png",
          "sizes": "192x192",
          "type": "image/png",
          "purpose": "any maskable"
        },
        {
          "src": "/icon-512.png",
          "sizes": "512x512",
          "type": "image/png",
          "purpose": "any maskable"
        }
      ]
    }

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
        
    return render_template("tenants.html", {
        "request": request,
        "user": user,
        "active_page": "tenants",
        "tenants": tenants
    }, db)

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
    
    return render_template("tenant_detail.html", {
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
    }, db)

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
    
    return render_template("staff.html", {
        "request": request,
        "user": user,
        "active_page": "staff",
        "staff": staff,
        "tenant": tenant
    }, db)

@router.get("/directory", response_class=HTMLResponse)
async def directory_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    users = db.query(User).order_by(User.id.desc()).all()
    push_devices = db.query(PushSubscription).order_by(PushSubscription.created_at.desc()).all()
    
    return render_template("directory.html", {
        "request": request,
        "user": user,
        "active_page": "directory",
        "users": users,
        "push_devices": push_devices
    }, db)

@router.post("/directory/devices/{device_id}/delete")
async def delete_device(device_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user or user.role != RoleEnum.SUPER_ADMIN:
        return RedirectResponse(url="/", status_code=303)
        
    device = db.query(PushSubscription).filter(PushSubscription.id == device_id).first()
    if device:
        db.delete(device)
        db.commit()
        
    return RedirectResponse(url="/directory", status_code=303)

from pydantic import BaseModel

class ToggleMuteRequest(BaseModel):
    visa_center_id: str

@router.post("/ui/preferences/toggle_mute")
async def toggle_mute(req: ToggleMuteRequest, request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    preferences = user.preferences or {}
    muted_centers = preferences.get("muted_visa_centers", [])
    
    if req.visa_center_id in muted_centers:
        muted_centers.remove(req.visa_center_id)
        is_muted = False
    else:
        muted_centers.append(req.visa_center_id)
        is_muted = True
        
    preferences["muted_visa_centers"] = muted_centers
    
    from sqlalchemy.orm.attributes import flag_modified
    user.preferences = preferences
    flag_modified(user, "preferences")
    
    db.commit()
    
    return {"status": "success", "is_muted": is_muted}
