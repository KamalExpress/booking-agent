from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import os
from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount
from models import SessionLocal

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
