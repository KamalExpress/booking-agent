from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from models import WorkerNode, Assignment, Lease, EventLog, ScraperAccount
from models import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def overview_page(request: Request, db: Session = Depends(get_db)):
    active_workers = db.query(WorkerNode).filter(WorkerNode.status == 'Active').count()
    active_assignments = db.query(Assignment).filter(Assignment.status == 'Leased').count()
    
    # Slots found in last 24h
    yesterday = datetime.utcnow() - timedelta(days=1)
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
    
    # Calculate online status (heartbeat < 3 mins ago)
    now = datetime.utcnow()
    for w in workers:
        if w.last_heartbeat and (now - w.last_heartbeat).total_seconds() < 180:
            w.is_online = True
        else:
            w.is_online = False
            
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
        
    return templates.TemplateResponse(
        request=request,
        name="assignments.html",
        context={
            "request": request,
            "active_page": "assignments",
            "assignments": assignments
        }
    )

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
