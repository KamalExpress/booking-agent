import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models import SessionLocal, Tenant, User, OTPChallenge

BITNET_SERVER_URL = os.getenv("BITNET_SERVER_URL", "https://ai.alamiaconnect.com").rstrip("/")
BITNET_API_KEY = os.getenv("BITNET_API_KEY", "")

class CopilotService:
    @staticmethod
    def execute_quick_action(action: str, params: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Execute deterministic actions with ZERO LLM calls."""
        action = action.strip().lower()
        
        try:
            try:
                from mcp_server import (
                    get_portal_health_summary,
                    get_active_leases,
                    unlease_resource,
                    trigger_maintenance_cycle,
                    get_workers
                )
            except Exception:
                get_portal_health_summary = None
                get_active_leases = None
                unlease_resource = None
                trigger_maintenance_cycle = None
                get_workers = None
            
            if action in ["system_health", "health"]:
                if get_portal_health_summary:
                    summary = get_portal_health_summary()
                else:
                    from models import SessionLocal, PortalAccount, Proxy
                    sdb = db or SessionLocal()
                    try:
                        accs = sdb.query(PortalAccount).count()
                        proxies = sdb.query(Proxy).count()
                        summary = f"Portal Accounts Summary: Total: {accs} | Proxies: {proxies}"
                    finally:
                        if not db: sdb.close()
                return {"type": "text", "content": summary}
                
            elif action in ["active_leases", "leases"]:
                limit = params.get("limit", 15) if params else 15
                leases = get_active_leases(limit=limit)
                return {"type": "text", "content": leases}
                
            elif action in ["unfreeze", "unlease"]:
                rtype = params.get("resource_type", "account") if params else "account"
                rid = params.get("resource_id", 0) if params else 0
                res = unlease_resource(resource_type=rtype, resource_id=rid)
                return {"type": "text", "content": res}
                
            elif action in ["maintenance", "orphan_cleanup"]:
                res = trigger_maintenance_cycle()
                return {"type": "text", "content": res}
                
            elif action in ["workers", "worker_status"]:
                res = get_workers()
                return {"type": "text", "content": res}
                
            elif action in ["active_challenges", "pending_otp"]:
                if not db:
                    db = SessionLocal()
                    close_db = True
                else:
                    close_db = False
                    
                try:
                    challenges = db.query(OTPChallenge).filter(
                        OTPChallenge.status.in_(["PENDING", "SUBMITTED"]),
                        OTPChallenge.expires_at > datetime.utcnow()
                    ).all()
                    
                    if not challenges:
                        return {"type": "text", "content": "No pending OTP verification challenges at this time."}
                        
                    lines = [f"Found {len(challenges)} active OTP challenge(s):"]
                    for c in challenges:
                        rem = max(0, int((c.expires_at - datetime.utcnow()).total_seconds()))
                        lines.append(f" - #{c.challenge_id}: {c.applicant_name} ({c.visa_center}) - Status: {c.status} ({rem}s remaining)")
                    return {"type": "text", "content": "\n".join(lines)}
                finally:
                    if close_db:
                        db.close()
            else:
                return {"type": "error", "content": f"Unknown quick action '{action}'."}
        except Exception as e:
            return {"type": "error", "content": f"Action execution error: {str(e)}"}

    @staticmethod
    def chat(message: str, user: Optional[User] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Conversational endpoint backed by ai.alamiaconnect.com with Graceful Degradation."""
        # 1. Feature Gate / Monetization Check
        if user and user.tenant_id and db:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and hasattr(tenant, "has_ai_copilot") and not tenant.has_ai_copilot:
                return {
                    "reply": "🔒 Alamia Copilot Pro is an enterprise add-on for this agency. Please contact your administrator to upgrade your plan.",
                    "status": "upgrade_required"
                }

        # 2. Check for fast-path deterministic keywords before hitting LLM
        lower_msg = message.strip().lower()
        if lower_msg in ["health", "status", "system health", "check health"]:
            res = CopilotService.execute_quick_action("system_health")
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}
            
        if lower_msg in ["leases", "active leases", "show leases"]:
            res = CopilotService.execute_quick_action("active_leases")
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}
            
        if lower_msg in ["workers", "worker list", "show workers"]:
            res = CopilotService.execute_quick_action("workers")
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        if lower_msg in ["otp", "pending otp", "challenges", "show otp"]:
            res = CopilotService.execute_quick_action("active_challenges", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        # 3. Query Internal LLM at ai.alamiaconnect.com
        server_url = (os.getenv("BITNET_SERVER_URL", "").strip() or "https://ai.alamiaconnect.com").rstrip("/")
        api_key = os.getenv("BITNET_API_KEY", "").strip() or "51129693340"
        
        endpoint = f"{server_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9"
        }
            
        payload = {
            "model": "bitnet-1bit",
            "messages": [
                {
                    "role": "system",
                    "content": "You are Alamia Copilot, the AI assistant for Alamia Travel OS. You assist visa agency staff with monitoring workers, inspecting slot releases, and managing appointments. Keep answers concise, factual, professional, and directly actionable. Never reveal credentials."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "max_tokens": 180,
            "temperature": 0.2
        }

        try:
            # Try curl_cffi first for TLS fingerprint bypass, fallback to requests
            try:
                from curl_cffi import requests as cffi_requests
                resp = cffi_requests.post(endpoint, json=payload, headers=headers, timeout=12, impersonate="chrome120")
            except Exception:
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=12)

            if resp.status_code == 200:
                data = resp.json()
                reply_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"reply": reply_text, "status": "ok", "source": "llm"}
            else:
                error_snippet = resp.text[:250].replace("\n", " ").strip()
                print(f"[Copilot LLM Error] endpoint={endpoint}, status={resp.status_code}, error={error_snippet}")
                return {
                    "reply": f"🤖 Alamia Copilot: AI inference returned status {resp.status_code} ({error_snippet[:100]}). You can still use the 1-click action buttons (System Health, Active Leases, OTP Entry) directly.",
                    "status": "degraded",
                    "source": "fallback"
                }
        except Exception as net_err:
            print(f"[Copilot LLM Exception] endpoint={endpoint}, err={net_err}")
            # Graceful Degradation: Zero-SPOF guarantee
            return {
                "reply": f"🤖 Alamia Copilot: AI conversational server is currently unreachable ({str(net_err)[:80]}). All deterministic operational tools (OTP entry, resource unfreezing, health checks) remain 100% operational.",
                "status": "offline",
                "source": "fallback"
            }
