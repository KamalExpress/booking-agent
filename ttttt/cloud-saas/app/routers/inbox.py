from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os

from models import SessionLocal, InboxMessage, User, Tenant, RoleEnum
from auth import get_current_user, get_current_user_from_cookie

router = APIRouter(tags=["Inbox"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_ui_user(request: Request, db: Session):
    try:
        return get_current_user_from_cookie(request, db)
    except HTTPException:
        return None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Schemas ---
class SendMessageRequest(BaseModel):
    tenant_id: int
    title: str
    body: str

class ReplyMessageRequest(BaseModel):
    body: str

# --- UI Routes ---
@router.get("/inbox", response_class=HTMLResponse)
async def inbox_page(request: Request, db: Session = Depends(get_db)):
    user = get_ui_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    messages_query = db.query(InboxMessage)
    
    if user.role != RoleEnum.SUPER_ADMIN:
        messages_query = messages_query.filter(InboxMessage.tenant_id == user.tenant_id)
        
    # Get top level threads
    messages = messages_query.filter(InboxMessage.parent_id == None).order_by(InboxMessage.created_at.desc()).all()
    
    tenants = []
    if user.role == RoleEnum.SUPER_ADMIN:
        tenants = db.query(Tenant).all()
        
    from routers.ui import render_template
    return render_template("inbox.html", {
        "request": request, 
        "user": user, 
        "messages": messages,
        "tenants": tenants
    }, db)

# --- API Routes ---
@router.post("/api/inbox/send")
def send_message(req: SendMessageRequest, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    if current_user.role != RoleEnum.SUPER_ADMIN and req.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot send message to another tenant")
        
    msg = InboxMessage(
        tenant_id=req.tenant_id,
        sender_id=current_user.id,
        title=req.title,
        body=req.body,
        is_system_alert=False,
        severity="info"
    )
    db.add(msg)
    db.commit()
    return {"status": "success", "message_id": msg.id}

@router.post("/api/inbox/{message_id}/reply")
def reply_message(message_id: int, req: ReplyMessageRequest, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    parent_msg = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not parent_msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if current_user.role != RoleEnum.SUPER_ADMIN and parent_msg.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to reply to this message")
        
    if parent_msg.is_system_alert:
        raise HTTPException(status_code=400, detail="Cannot reply to system alerts")
        
    reply = InboxMessage(
        tenant_id=parent_msg.tenant_id,
        sender_id=current_user.id,
        parent_id=parent_msg.id,
        title=f"Re: {parent_msg.title}",
        body=req.body,
        is_system_alert=False,
        severity="info"
    )
    db.add(reply)
    db.commit()
    return {"status": "success", "reply_id": reply.id}

@router.put("/api/inbox/{message_id}/read")
def mark_read(message_id: int, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    msg = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if current_user.role != RoleEnum.SUPER_ADMIN and msg.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    msg.is_read = True
    db.commit()
    return {"status": "success"}
