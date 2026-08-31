import os
import requests
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from models import SessionLocal, Tenant, User, OTPChallenge, SlotAvailability, WorkerNode, Proxy, PortalAccount
import services.travelos_capabilities as caps

BITNET_SERVER_URL = os.getenv("BITNET_SERVER_URL", "https://ai.alamiaconnect.com").rstrip("/")
BITNET_API_KEY = os.getenv("BITNET_API_KEY", "51129693340")

class CopilotService:
    @staticmethod
    def execute_quick_action(action: str, params: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Execute deterministic actions with ZERO LLM calls (Fast-Path / 1-Click Chips)."""
        action = action.strip().lower()
        
        try:
            if action in ["system_health", "health"]:
                summary = caps.get_portal_health_summary(db=db)
                return {"type": "text", "content": summary}
                
            elif action in ["active_leases", "leases"]:
                limit = params.get("limit", 15) if params else 15
                leases = caps.get_active_leases(limit=limit, db=db)
                return {"type": "text", "content": leases}
                
            elif action in ["workers", "worker_list", "fleet"]:
                workers_summary = caps.get_workers(db=db)
                return {"type": "text", "content": workers_summary}

            elif action in ["slots", "slot_availability", "slots_available"]:
                visa_center = params.get("visa_center") if params else None
                slots_summary = caps.get_available_slots(visa_center=visa_center, db=db)
                return {"type": "text", "content": slots_summary}

            elif action in ["proxy_health", "proxies"]:
                proxy_summary = caps.get_proxy_health(db=db)
                return {"type": "text", "content": proxy_summary}

            elif action in ["unfreeze", "unlease"]:
                rtype = params.get("resource_type", "account") if params else "account"
                rid = params.get("resource_id", 0) if params else 0
                res = caps.unlease_resource(resource_type=rtype, resource_id=rid, db=db)
                return {"type": "text", "content": res}
                
            elif action in ["maintenance", "orphan_cleanup"]:
                res = caps.trigger_maintenance_cycle(db=db)
                return {"type": "text", "content": res}
                
            elif action in ["active_challenges", "pending_otp", "challenges"]:
                sdb = db or SessionLocal()
                try:
                    challenges = sdb.query(OTPChallenge).filter(
                        OTPChallenge.status.in_(["PENDING", "SUBMITTED"]),
                        OTPChallenge.expires_at > datetime.utcnow()
                    ).all()
                    
                    if not challenges:
                        return {"type": "text", "content": "No pending OTP verification challenges at this time."}
                        
                    lines = [f"Found {len(challenges)} active OTP challenge(s):"]
                    for c in challenges:
                        rem = max(0, int((c.expires_at - datetime.utcnow()).total_seconds()))
                        lines.append(f" • #{c.challenge_id}: {c.applicant_name} (Center {c.visa_center}) - Status: {c.status} ({rem}s remaining)")
                    return {"type": "text", "content": "\n".join(lines)}
                finally:
                    if not db: sdb.close()
            else:
                return {"type": "error", "content": f"Unknown quick action '{action}'."}
        except Exception as e:
            return {"type": "error", "content": f"Action execution error: {str(e)}"}

    @staticmethod
    def _parse_tool_call(llm_output: str) -> Optional[Dict[str, Any]]:
        """Parses ACTION: tool_name(args) or ACTION: {"tool": ..., "args": ...} from BitNet."""
        text = llm_output.strip()
        if "ACTION:" not in text and "action:" not in text.lower():
            return None
            
        action_match = re.search(r"ACTION:\s*([a-zA-Z0-9_\.]+)\s*(\([^\)]*\))?", text, re.IGNORECASE)
        if not action_match:
            # Check for JSON format
            json_match = re.search(r"ACTION:\s*(\{.*\})", text, re.DOTALL | re.IGNORECASE)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    return {"tool": data.get("tool"), "args": data.get("args", {})}
                except Exception:
                    pass
            return None
            
        tool_name = action_match.group(1).strip()
        args_str = action_match.group(2)
        args = {}
        
        if args_str:
            args_clean = args_str.strip("()")
            if args_clean:
                # Check for json object in parenthesis
                if args_clean.startswith("{") and args_clean.endswith("}"):
                    try:
                        args = json.loads(args_clean)
                    except Exception:
                        pass
                else:
                    # Parse simple positional/named argument e.g. ("worker_17") or (worker_id="worker_17")
                    if "=" in args_clean:
                        for part in args_clean.split(","):
                            if "=" in part:
                                k, v = part.split("=", 1)
                                args[k.strip().strip("'\"")] = v.strip().strip("'\"")
                    else:
                        val = args_clean.strip().strip("'\"")
                        if "worker" in tool_name:
                            args["worker_id"] = val
                        elif "slot" in tool_name:
                            args["visa_center"] = val
                            
        return {"tool": tool_name, "args": args}

    @staticmethod
    def _call_bitnet(messages: List[Dict[str, str]], max_tokens: int = 180, temperature: float = 0.2) -> Dict[str, Any]:
        """Executes HTTP inference call to ai.alamiaconnect.com with WAF bypass headers."""
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
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            try:
                from curl_cffi import requests as cffi_requests
                resp = cffi_requests.post(endpoint, json=payload, headers=headers, timeout=25, impersonate="chrome120")
            except Exception:
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=25)

            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"status": "ok", "content": content}
            else:
                err_snip = resp.text[:150].replace("\n", " ").strip()
                return {"status": "error", "content": f"Status {resp.status_code}: {err_snip}"}
        except Exception as e:
            return {"status": "offline", "content": str(e)}

    @staticmethod
    def chat(message: str, user: Optional[User] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Conversational endpoint bridging TravelOS Copilot with BitNet and TravelOS MCP Capabilities."""
        # 1. Feature Gate / Enterprise Monetization Check
        if user and user.tenant_id and db:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and hasattr(tenant, "has_ai_copilot") and not tenant.has_ai_copilot:
                return {
                    "reply": "🔒 Alamia Copilot Pro is an enterprise add-on for this agency. Please contact your administrator to upgrade your plan.",
                    "status": "upgrade_required"
                }

        lower_msg = message.strip().lower()

        # 2. Tier 1: Deterministic Fast Paths (0 LLM Tokens, 0.01s Latency)
        if any(k in lower_msg for k in ["any slot", "slots available", "check slot", "show slot", "are there slot", "is there a slot", "slots today", "available today", "open slot"]):
            res = CopilotService.execute_quick_action("slot_availability", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        if any(k in lower_msg for k in ["proxy", "proxies", "proxy health", "check proxy"]):
            res = CopilotService.execute_quick_action("proxy_health", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        if lower_msg in ["health", "status", "system health", "check health"]:
            res = CopilotService.execute_quick_action("system_health", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}
            
        if lower_msg in ["leases", "active leases", "show leases"]:
            res = CopilotService.execute_quick_action("active_leases", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}
            
        if lower_msg in ["workers", "worker list", "show workers", "fleet"]:
            res = CopilotService.execute_quick_action("workers", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        if lower_msg in ["otp", "pending otp", "challenges", "show otp"]:
            res = CopilotService.execute_quick_action("active_challenges", db=db)
            return {"reply": res["content"], "status": "ok", "source": "deterministic"}

        # 3. Tier 2: Structured Agent Loop with TravelOS Capabilities
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        # Step 3.1: Stable System Instructions (Owned by TravelOS Copilot)
        system_rules = (
            "You are Alamia TravelOS Copilot, the operational assistant for TravelOS.\n"
            "Answer factually and concisely (under 2 sentences).\n"
            "If operational data is needed, reply ONLY with:\n"
            "ACTION: <tool_name>(<arguments>)\n"
            "When an OBSERVATION is given, base your answer strictly on it."
        )
        
        # Step 3.2: Dynamic Context & Targeted Tool Declarations
        relevant_tools = caps.filter_relevant_tools(message)
        tool_sigs = caps.format_tool_declarations(relevant_tools)
        
        context_prompt = (
            f"Current Time: {now_utc}\n"
            f"{tool_sigs}"
        )
        
        messages = [
            {"role": "system", "content": system_rules},
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": message}
        ]
        
        # Step 3.3: First Inference Hop (Intent & Action Evaluation)
        call_res = CopilotService._call_bitnet(messages, max_tokens=100, temperature=0.1)
        
        if call_res["status"] != "ok":
            return {
                "reply": f"🤖 Alamia Copilot: AI inference is currently unreachable ({call_res['content'][:80]}). All deterministic operational tools (Slots, Health, OTP Entry) remain 100% operational.",
                "status": "offline",
                "source": "fallback"
            }
            
        first_reply = call_res["content"].strip()
        tool_call = CopilotService._parse_tool_call(first_reply)
        
        # If no tool requested, return BitNet's direct conversational answer
        if not tool_call:
            return {"reply": first_reply, "status": "ok", "source": "llm"}
            
        # Step 3.4: Execute TravelOS Capability in Cloud SaaS Runtime
        tool_name = tool_call["tool"]
        tool_args = tool_call["args"]
        print(f"[Copilot Agent Loop] BitNet requested tool: {tool_name}({tool_args})")
        
        observation = caps.execute_capability(tool_name, tool_args, db=db)
        print(f"[Copilot Agent Loop] Tool observation: {observation[:120]}...")
        
        # Step 3.5: Feed Observation Back to BitNet for Final Synthesis
        synthesis_rules = (
            "You are Alamia TravelOS Copilot, the operational assistant for TravelOS.\n"
            "You have performed the tool investigation. Using the OBSERVATION provided, "
            "provide a concise, direct, and factual explanation to the user in 1-2 sentences. "
            "Do NOT output any ACTION commands. Provide your normal natural language answer."
        )
        synthesis_messages = [
            {"role": "system", "content": synthesis_rules},
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"ACTION: {tool_name}({json.dumps(tool_args)})"},
            {"role": "user", "content": f"OBSERVATION: {observation}\n\nExplain the observation to answer the user question."}
        ]
        
        synth_res = CopilotService._call_bitnet(synthesis_messages, max_tokens=150, temperature=0.2)
        if synth_res["status"] == "ok":
            final_reply = synth_res["content"].strip()
            # Safety filter in case model still outputs an ACTION prefix
            if final_reply.startswith("ACTION:"):
                return {"reply": f"Based on live logs: {observation}", "status": "ok", "source": "tool_direct"}
            return {"reply": final_reply, "status": "ok", "source": "agent_loop"}
        else:
            # If second hop failed, return the raw observation
            return {"reply": f"{observation}", "status": "ok", "source": "tool_direct"}
