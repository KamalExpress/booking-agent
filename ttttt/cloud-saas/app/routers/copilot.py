from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from models import get_db, User
from auth import get_current_user_from_cookie
from services.copilot_service import CopilotService

router = APIRouter(prefix="/api/v1/copilot", tags=["Alamia Copilot"])

class ChatRequest(BaseModel):
    message: str
    action: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

@router.post("/chat")
def chat_with_copilot(
    req: ChatRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Chat endpoint supporting both 1-click deterministic actions and semantic LLM queries."""
    if req.action:
        # Deterministic 1-click action: 0 LLM calls
        result = CopilotService.execute_quick_action(req.action, req.params, db=db)
        return {
            "reply": result["content"],
            "status": "ok",
            "source": "deterministic"
        }
        
    # Free-text semantic chat with graceful degradation
    return CopilotService.chat(req.message, user=current_user, db=db)

@router.get("/status")
def get_copilot_status(current_user: User = Depends(get_current_user_from_cookie)):
    """Check availability of internal LLM inference."""
    import os, requests
    server_url = os.getenv("BITNET_SERVER_URL", "https://ai.alamiaconnect.com").rstrip("/")
    try:
        r = requests.get(f"{server_url}/health", timeout=1.5)
        is_online = (r.status_code == 200)
    except Exception:
        is_online = False
        
    return {
        "copilot_name": "Alamia Copilot",
        "llm_server": server_url,
        "llm_online": is_online,
        "hitl_deterministic_engine": "online"
    }
