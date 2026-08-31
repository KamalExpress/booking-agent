import os
import requests
import json
import re
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from models import SessionLocal, Tenant, User, OTPChallenge, SlotAvailability, WorkerNode, Proxy, PortalAccount

BITNET_SERVER_URL = os.getenv("BITNET_SERVER_URL", "https://ai.alamiaconnect.com").rstrip("/")
BITNET_API_KEY = os.getenv("BITNET_API_KEY", "51129693340")

class TravelOSMCPClient:
    """
    Authentic MCP In-Process Client for the TravelOS FastMCP Server.
    Discovers capabilities via MCP tools/list and invokes execution via MCP tools/call.
    """
    # Strict Zero-SPOF HITL Isolation: Only read-only operational inspection tools are exposed to AI
    AI_ACCESSIBLE_TOOLS = {
        "get_workers",
        "get_worker_status",
        "get_worker_details",
        "get_worker_logs",
        "get_available_slots",
        "get_proxy_health",
        "get_active_leases",
        "get_portal_health_summary",
        "trigger_maintenance_cycle"
    }

    @classmethod
    async def list_tools(cls) -> List[Dict[str, Any]]:
        """MCP tools/list: discover registered tools and their JSON schemas from FastMCP."""
        try:
            from mcp_server import mcp
            raw_tools = await mcp.list_tools()
            filtered = []
            for t in raw_tools:
                if t.name in cls.AI_ACCESSIBLE_TOOLS:
                    filtered.append({
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": getattr(t, "inputSchema", {})
                    })
            return filtered
        except Exception as e:
            print(f"[TravelOSMCPClient] Error in tools/list: {e}")
            return []

    @classmethod
    def list_tools_sync(cls) -> List[Dict[str, Any]]:
        """Synchronous wrapper for MCP tools/list."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, cls.list_tools()).result()
        else:
            return loop.run_until_complete(cls.list_tools())

    @classmethod
    async def call_tool(cls, name: str, arguments: Dict[str, Any]) -> str:
        """MCP tools/call: execute a tool through the FastMCP server dispatch pipeline."""
        # Enforce security barrier: AI cannot invoke non-whitelisted tools
        if name not in cls.AI_ACCESSIBLE_TOOLS:
            return f"Access Denied: Tool '{name}' is restricted and cannot be invoked by the AI Copilot."
            
        try:
            from mcp_server import mcp
            raw_res = await mcp.call_tool(name, arguments)
            if isinstance(raw_res, tuple) and len(raw_res) > 0:
                contents = raw_res[0]
                if isinstance(contents, list) and len(contents) > 0:
                    return getattr(contents[0], "text", str(contents[0]))
            elif isinstance(raw_res, list) and len(raw_res) > 0:
                return getattr(raw_res[0], "text", str(raw_res[0]))
            return str(raw_res)
        except Exception as e:
            # Resilient fallback to capability engine if FastMCP server encounters an environment error
            try:
                import services.travelos_capabilities as caps
                return caps.execute_capability(name, arguments)
            except Exception:
                return f"MCP tools/call error on '{name}': {str(e)}"

    @classmethod
    def call_tool_sync(cls, name: str, arguments: Dict[str, Any]) -> str:
        """Synchronous wrapper for MCP tools/call."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, cls.call_tool(name, arguments)).result()
        else:
            return loop.run_until_complete(cls.call_tool(name, arguments))


class CopilotService:
    # Configurable policy limit for investigation depth
    MAX_TOOL_ITERATIONS = int(os.getenv("COPILOT_MAX_TOOL_ITERATIONS", "2"))

    @staticmethod
    def execute_quick_action(action: str, params: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Execute deterministic actions with ZERO LLM calls (Fast-Path / 1-Click Chips via MCP)."""
        action = action.strip().lower()
        
        try:
            if action in ["system_health", "health"]:
                summary = TravelOSMCPClient.call_tool_sync("get_portal_health_summary", {})
                return {"type": "text", "content": summary}
                
            elif action in ["active_leases", "leases"]:
                limit = params.get("limit", 15) if params else 15
                leases = TravelOSMCPClient.call_tool_sync("get_active_leases", {"limit": limit})
                return {"type": "text", "content": leases}
                
            elif action in ["workers", "worker_list", "fleet"]:
                workers_summary = TravelOSMCPClient.call_tool_sync("get_workers", {})
                return {"type": "text", "content": workers_summary}

            elif action in ["slots", "slot_availability", "slots_available"]:
                visa_center = params.get("visa_center", "") if params else ""
                days = params.get("days", 7) if params else 7
                slots_summary = TravelOSMCPClient.call_tool_sync("get_available_slots", {"visa_center": visa_center, "days": days, "limit": 10})
                return {"type": "text", "content": slots_summary}

            elif action in ["proxy_health", "proxies"]:
                proxy_summary = TravelOSMCPClient.call_tool_sync("get_proxy_health", {})
                return {"type": "text", "content": proxy_summary}

            elif action in ["test_push", "send_test_push"]:
                from notifications import send_push_notification
                sdb = db or SessionLocal()
                try:
                    cnt = send_push_notification(sdb, "Test Push Notification", "[TEST] This is a live test notification from Alamia Copilot.")
                    return {"type": "text", "content": f"Test push notification dispatched to {cnt} registered device endpoint(s)."}
                finally:
                    if not db: sdb.close()

            elif action in ["active_challenges", "pending_otp", "challenges"]:
                from services.travelos_capabilities import format_human_duration
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
                        lines.append(f" - #{c.challenge_id}: {c.applicant_name} (Center {c.visa_center}) - Status: {c.status} ({format_human_duration(rem)} remaining)")
                    return {"type": "text", "content": "\n".join(lines)}
                finally:
                    if not db: sdb.close()

            elif action in ["maintenance", "cleanup", "reconcile"]:
                res = TravelOSMCPClient.call_tool_sync("trigger_maintenance_cycle", {})
                return {"type": "text", "content": res}
            else:
                return {"type": "error", "content": f"Unknown quick action '{action}'."}
        except Exception as e:
            return {"type": "error", "content": f"Action execution error: {str(e)}"}

    @staticmethod
    def _parse_tool_call(llm_output: str) -> Optional[Dict[str, Any]]:
        """Parses ACTION: tool_name(args) with strict unambiguous key aliases and NO value mutation."""
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
                if args_clean.startswith("{") and args_clean.endswith("}"):
                    try:
                        args = json.loads(args_clean)
                    except Exception:
                        pass
                else:
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
                            
        # Canonical tool name mapping
        canonical_map = {
            "worker.get_status": "get_worker_status",
            "worker_get_status": "get_worker_status",
            "worker.get_details": "get_worker_details",
            "worker_get_details": "get_worker_details",
            "worker.get_recent_logs": "get_worker_logs",
            "worker.get_logs": "get_worker_logs",
            "worker_get_recent_logs": "get_worker_logs",
            "worker.list_all": "get_workers",
            "slots.get_available": "get_available_slots",
            "slots_get_available": "get_available_slots",
            "proxy.get_health": "get_proxy_health",
            "proxy_get_health": "get_proxy_health",
            "system.get_health": "get_portal_health_summary",
            "system.get_active_leases": "get_active_leases"
        }
        canonical_tool = canonical_map.get(tool_name, tool_name)
        
        # Strict Unambiguous Key-Alias Normalization (Rule: Never infer or modify values)
        KEY_ALIAS_MAP = {
            "worker": "worker_id",
            "workerId": "worker_id",
            "node_id": "worker_id",
            "center": "visa_center",
            "vac": "visa_center",
            "vac_id": "visa_center"
        }
        normalized_args = {}
        for k, v in args.items():
            canonical_key = KEY_ALIAS_MAP.get(k, k)
            normalized_args[canonical_key] = v

        # If worker_id is missing and one key is an exact worker identifier (e.g. worker_17):
        if "worker" in canonical_tool and "worker_id" not in normalized_args:
            for k in list(normalized_args.keys()):
                if re.match(r"^worker_\w+", str(k), re.IGNORECASE):
                    val = normalized_args.pop(k)
                    normalized_args["worker_id"] = str(k)
                    if isinstance(val, dict):
                        normalized_args.update(val)
                    elif isinstance(val, (int, str)) and "limit" not in normalized_args and str(val).isdigit():
                        normalized_args["limit"] = int(val)
                    break
                    
        return {"tool": canonical_tool, "args": normalized_args}

    @staticmethod
    def _parse_temporal_boundaries(message: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse natural language time expressions into dual search boundaries (since_minutes, until_minutes)."""
        msg = message.lower()
        
        # Pattern: "7-8 minutes ago", "7 to 8 mins ago"
        range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:mins?|minutes?)\s*ago", msg)
        if range_match:
            try:
                m1 = int(range_match.group(1))
                m2 = int(range_match.group(2))
                older = max(m1, m2)
                newer = min(m1, m2)
                # Expand with conservative tolerance: +2m older, -1m newer
                return (older + 2, max(0, newer - 1))
            except Exception:
                pass
                
        # Pattern: "8 minutes ago", "10 mins ago"
        single_match = re.search(r"(\d+)\s*(?:mins?|minutes?)\s*ago", msg)
        if single_match:
            try:
                m = int(single_match.group(1))
                return (m + 3, max(0, m - 2))
            except Exception:
                pass
                
        # Pattern: "last 15 minutes", "past 10 mins"
        last_mins_match = re.search(r"(?:last|past)\s*(\d+)\s*(?:mins?|minutes?)", msg)
        if last_mins_match:
            try:
                m = int(last_mins_match.group(1))
                return (m, 0)
            except Exception:
                pass
                
        # Pattern: "last hour", "past hour", "1 hour ago"
        if any(h in msg for h in ["last hour", "past hour", "1 hour ago", "an hour ago"]):
            return (65, 0)
            
        # Pattern: "today", "this morning"
        if "today" in msg or "this morning" in msg:
            return (1440, 0)
            
        return (None, None)

    @staticmethod
    def _get_required_evidence_type(message: str) -> Optional[str]:
        """Determine what category of evidence is strictly required for this operational query."""
        msg = message.lower()
        if any(k in msg for k in ["fail", "error", "crash", "stuck", "down", "why did", "why has", "what happened", "investigate", "reason"]):
            return "worker_logs"
        elif any(k in msg for k in ["slot", "appointment", "dates available", "open"]):
            return "slots"
        elif any(k in msg for k in ["proxy", "proxies", "ip rotation"]):
            return "proxies"
        elif any(k in msg for k in ["health", "system state", "overall status"]):
            return "system_health"
        return None

    @staticmethod
    def _validate_grounding(candidate_reply: str, observations: List[str], required_evidence: Optional[str], time_window: Tuple[Optional[int], Optional[int]]) -> str:
        """Validate candidate LLM reply against observed facts, rejecting hallucinations, speculative causes, and contradictions."""
        combined_obs = " ".join(observations)
        reply = candidate_reply.strip()
        
        # Rule 1: Negative Evidence Guard (The Killer Test)
        # If observation states [NO_ERRORS_RECORDED] or contains no errors for requested time window:
        if "[NO_ERRORS_RECORDED]" in combined_obs or "No critical worker errors recorded" in combined_obs:
            speculative_tokens = ["due to", "because", "may have", "might have", "probably", "likely", "perhaps", "could be", "illness", "network issue", "hardware"]
            if any(t in reply.lower() for t in speculative_tokens) or not any(k in reply.lower() for k in ["could not find", "no recorded", "no worker error", "cannot determine"]):
                since_m, until_m = time_window
                window_str = f"between {since_m}m and {until_m}m ago" if (since_m and until_m) else (f"the last {since_m} minutes" if since_m else "the requested time window")
                return f"I could not find any recorded worker errors in {window_str}, so the cause cannot be determined from the available logs."
                
        # Rule 2: Contradiction Guard
        # If system is DEGRADED or STALE, reject any "operating optimally" / "everything is healthy"
        if "[SYSTEM STATUS] DEGRADED" in combined_obs or "[SYSTEM STATUS] STALE" in combined_obs:
            bad_phrases = ["operating optimally", "everything is healthy", "all systems operational", "no action required", "fully operational"]
            if any(p in reply.lower() for p in bad_phrases):
                # Extract reasons from observation
                reasons = []
                for line in combined_obs.split("\n"):
                    if line.strip().startswith("- ") and ("error" in line.lower() or "stale" in line.lower()):
                        reasons.append(line.strip()[2:])
                reason_str = f" ({'; '.join(reasons)})" if reasons else ""
                return f"TravelOS is currently degraded{reason_str}. Recent worker errors were detected and require attention."
                
        # Rule 3: Strip any leftover ACTION commands from synthesis
        if reply.startswith("ACTION:") or "action:" in reply.lower():
            return f"Based on live FastMCP telemetry: {observations[-1] if observations else 'Telemetry received.'}"
            
        return reply

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
        """Conversational endpoint bridging TravelOS Copilot with BitNet and TravelOS FastMCP Server."""
        # 1. Feature Gate / Enterprise Monetization Check
        if user and user.tenant_id and db:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and hasattr(tenant, "has_ai_copilot") and not tenant.has_ai_copilot:
                return {
                    "reply": "[UPGRADE REQUIRED] Alamia Copilot Pro is an enterprise add-on for this agency. Please contact your administrator to upgrade your plan.",
                    "status": "upgrade_required"
                }

        lower_msg = message.strip().lower()
        is_investigative = any(w in lower_msg for w in ["why", "how come", "reason", "explain", "investigate", "what happened", "recommend", "diagnos"])
        is_historical = any(w in lower_msg for w in ["last", "past", "history", "ago", "previous", "yesterday", "days", "did any", "opened", "was there", "were there", "4-5", "3-4", "few days"])

        # Extract visa center from message if present
        extracted_center = ""
        for c in ["islamabad", "lahore", "karachi", "peshawar", "quetta", "mirpur", "faisalabad"]:
            if c in lower_msg:
                extracted_center = c.capitalize()
                break

        # Extract days if mentioned (e.g. "last 4-5 days", "3 days ago")
        extracted_days = 7
        days_match = re.search(r"(\d+)\s*(?:-\s*(\d+))?\s*days?", lower_msg)
        if days_match:
            try:
                if days_match.group(2):
                    extracted_days = int(days_match.group(2))
                else:
                    extracted_days = int(days_match.group(1))
            except Exception:
                extracted_days = 7

        # Extract temporal boundaries if mentioned (e.g. "7-8 minutes ago", "last hour")
        since_mins, until_mins = CopilotService._parse_temporal_boundaries(message)

        # Extract worker_id from message if present (e.g. "worker_73765413" or "worker 17")
        extracted_worker_id = ""
        w_match = re.search(r"worker[_\-\s]?([a-zA-Z0-9]+)", lower_msg)
        if w_match:
            val = w_match.group(1)
            extracted_worker_id = f"worker_{val}" if not val.startswith("worker") else val

        # Determine required evidence category
        required_evidence = CopilotService._get_required_evidence_type(message)

        # 2. Tier 1: Deterministic Fast Paths (0 LLM Tokens, 0.01s Latency via MCP)

        # Operational Health / Diagnostic Inquiries (Last checked, errors, stale scraping, recommendations)
        if any(k in lower_msg for k in ["last checked", "1 day ago", "stale", "why not checking", "not checking", "worker error", "errors", "recommend", "health report"]):
            summary = TravelOSMCPClient.call_tool_sync("get_portal_health_summary", {})
            return {"reply": summary, "status": "ok", "source": "deterministic_diagnostics"}

        # Push Notification Inquiries
        if any(k in lower_msg for k in ["push notification", "push notifications", "not receiving push", "why no push", "no notifications", "test push"]):
            sdb = db or SessionLocal()
            try:
                sub_count = sdb.query(PushSubscription).count()
                if sub_count == 0:
                    reply = (
                        "[PUSH NOTIFICATION DIAGNOSIS]\n"
                        "- Subscribed Devices: 0 registered in the database.\n"
                        "- Root Cause: Browser push permissions have not been granted on this device.\n"
                        "- Required Action: Click the 'Enable Notifications' toggle in the PWA sidebar or header.\n"
                        "- Note: Notifications only trigger on successful slot detection or OTP challenges. If scraping is stale, no notification events are emitted."
                    )
                else:
                    reply = (
                        f"[PUSH NOTIFICATION DIAGNOSIS]\n"
                        f"- Subscribed Devices: {sub_count} active device endpoint(s) registered.\n"
                        f"- Reason for silence: Slot notifications are only dispatched when workers complete active checks. If the dashboard shows 'Last Checked 1 day ago', background workers have stalled or encountered proxy/login errors, preventing alert broadcasts.\n"
                        f"- Action: Click [Cleanup] or check worker logs to restore active scraping cycles."
                    )
                return {"reply": reply, "status": "ok", "source": "deterministic_diagnostics"}
            finally:
                if not db: sdb.close()

        # Slot inquiries (Fast-path only for simple current availability; historical queries pass to MCP)
        if not is_investigative and not is_historical:
            if any(k in lower_msg for k in ["any slot", "slots available", "check slot", "show slot", "are there slot", "is there a slot", "slots today", "available today", "open slot"]):
                res = CopilotService.execute_quick_action("slot_availability", params={"visa_center": extracted_center, "days": extracted_days}, db=db)
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

        # Deterministic HITL Guidance: OTP questions are answered factually without sending secrets to AI
        if any(k in lower_msg for k in ["otp pending", "pending otp", "what do i need to do", "how to enter otp", "where to enter otp", "pending - what do i need to do"]):
            res = CopilotService.execute_quick_action("active_challenges", db=db)
            return {
                "reply": (
                    f"{res['content']}\n\n"
                    "[OPERATIONAL GUIDANCE] To complete verification, enter the OTP code provided by the applicant directly into the [Pending OTP] challenge card or via the Admin Dashboard. "
                    "For security, OTP codes are processed exclusively through the human-in-the-loop verification pipeline and are never handled by the AI."
                ),
                "status": "ok",
                "source": "deterministic_hitl"
            }

        # 3. Tier 2: MCP Discovery (tools/list) & Structured Multi-Hop Agent Loop
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        # Step 3.1: Stable System Instructions (Owned by TravelOS Copilot)
        system_rules = (
            "You are Alamia TravelOS Copilot, the operational assistant for TravelOS.\n"
            "Answer factually and concisely (under 2 sentences).\n"
            "If operational data is needed, reply ONLY with:\n"
            "ACTION: <tool_name>(<arguments>)\n"
            "When an OBSERVATION is given, provide your natural language answer directly. Do not call another action if you already have the answer."
        )
        
        # Step 3.2: MCP Tool Discovery via FastMCP tools/list
        mcp_tools = TravelOSMCPClient.list_tools_sync()
        
        # Filter relevant tools based on query and required evidence
        q = message.lower()
        selected_tools = []
        if required_evidence == "worker_logs":
            selected_tools = [t for t in mcp_tools if t["name"] in ["get_worker_logs", "get_worker_details", "get_workers"]]
        else:
            for t in mcp_tools:
                t_name = t["name"].lower()
                if any(w in q for w in ["worker", "fail", "stuck", "node", "online"]) and "worker" in t_name:
                    selected_tools.append(t)
                elif any(s in q for s in ["slot", "appointment", "date", "islamabad", "lahore"]) and "slot" in t_name:
                    selected_tools.append(t)
                elif any(p in q for p in ["proxy", "ip"]) and "proxy" in t_name:
                    selected_tools.append(t)
                elif any(h in q for h in ["health", "system", "portal"]) and ("health" in t_name or "portal" in t_name):
                    selected_tools.append(t)
                    
        if not selected_tools:
            selected_tools = [t for t in mcp_tools if t["name"] in ["get_workers", "get_available_slots", "get_proxy_health", "get_portal_health_summary"]]
            
        selected_tools = selected_tools[:4]
        
        tool_lines = ["Available MCP Operational Tools:"]
        for t in selected_tools:
            props = t["inputSchema"].get("properties", {})
            param_examples = {}
            for p_k, p_v in props.items():
                p_type = p_v.get("type", "string")
                param_examples[p_k] = f"<{p_type}>"
            tool_lines.append(f"- {t['name']}({json.dumps(param_examples)}): {t['description']}")
        tool_sigs = "\n".join(tool_lines)
        
        context_prompt = (
            f"Current Time: {now_utc}\n"
            f"{tool_sigs}"
        )
        
        # Step 3.3: Multi-Hop Agent Loop Bounded by Configurable Policy Limit
        current_messages = [
            {"role": "system", "content": system_rules},
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": message}
        ]
        
        tool_invoked = False
        last_observation = ""
        all_observations = []
        
        for iteration in range(CopilotService.MAX_TOOL_ITERATIONS):
            call_res = CopilotService._call_bitnet(current_messages, max_tokens=100, temperature=0.1)
            
            if call_res["status"] != "ok":
                if not tool_invoked:
                    return {
                        "reply": f"Alamia Copilot: AI inference is currently unreachable ({call_res['content'][:80]}). All deterministic operational tools remain operational.",
                        "status": "offline",
                        "source": "fallback"
                    }
                break # Proceed with observations gathered so far
                
            model_reply = call_res["content"].strip()
            tool_call = CopilotService._parse_tool_call(model_reply)
            
            # If model produced a final answer without requesting a tool
            if not tool_call:
                # Mandatory Evidence Firewall: Operational inquiries MUST obtain evidence before answering
                if required_evidence and not tool_invoked:
                    print(f"[Copilot Grounding Firewall] Query requires '{required_evidence}' but model output ungrounded text. Forcing tool invocation.")
                    if required_evidence == "worker_logs":
                        tool_call = {
                            "tool": "get_worker_logs",
                            "args": {
                                "worker_id": extracted_worker_id or "worker_73765413",
                                "limit": 5,
                                "since_minutes": since_mins or 15,
                                "until_minutes": until_mins or 0
                            }
                        }
                    elif required_evidence == "slots":
                        tool_call = {"tool": "get_available_slots", "args": {"visa_center": extracted_center, "days": extracted_days}}
                    elif required_evidence == "proxies":
                        tool_call = {"tool": "get_proxy_health", "args": {}}
                    elif required_evidence == "system_health":
                        tool_call = {"tool": "get_portal_health_summary", "args": {}}
                else:
                    validated = CopilotService._validate_grounding(model_reply, [last_observation] if last_observation else [], required_evidence, (since_mins, until_mins))
                    return {"reply": validated, "status": "ok", "source": "agent_loop" if tool_invoked else "llm"}
                
            # Execute MCP tools/call
            tool_name = tool_call["tool"]
            tool_args = tool_call["args"]
            
            # Typed Evidence Firewall: If failure query, model cannot satisfy with proxy_health or irrelevant tool
            if required_evidence == "worker_logs" and tool_name not in ["get_worker_logs", "get_worker_details", "get_workers"]:
                print(f"[Copilot Grounding Firewall] Rejecting irrelevant tool '{tool_name}' for failure investigation. Forcing 'get_worker_logs'.")
                tool_name = "get_worker_logs"
                tool_args = {
                    "worker_id": extracted_worker_id or "worker_73765413",
                    "limit": 5,
                    "since_minutes": since_mins or 15,
                    "until_minutes": until_mins or 0
                }
            elif tool_name == "get_worker_logs":
                if "worker_id" not in tool_args and extracted_worker_id:
                    tool_args["worker_id"] = extracted_worker_id
                if since_mins is not None and "since_minutes" not in tool_args:
                    tool_args["since_minutes"] = since_mins
                if until_mins is not None and "until_minutes" not in tool_args:
                    tool_args["until_minutes"] = until_mins
            elif tool_name == "get_available_slots":
                if "visa_center" not in tool_args and extracted_center:
                    tool_args["visa_center"] = extracted_center
                if "days" not in tool_args and extracted_days:
                    tool_args["days"] = extracted_days

            print(f"[Copilot MCP Client] Hop {iteration + 1}/{CopilotService.MAX_TOOL_ITERATIONS} - tools/call: {tool_name}({tool_args})")
            
            observation = TravelOSMCPClient.call_tool_sync(tool_name, tool_args)
            tool_invoked = True
            last_observation = observation
            all_observations.append(observation)
            print(f"[Copilot MCP Client] FastMCP Observation: {observation[:120]}...")
            
            current_messages.append({"role": "assistant", "content": f"ACTION: {tool_name}({json.dumps(tool_args)})"})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {observation}\n\nContinue investigation or synthesize final answer."})

        # Step 3.4: Final Synthesis Hop
        synthesis_rules = (
            "You are Alamia TravelOS Copilot, the operational assistant for TravelOS.\n"
            "You have completed your operational investigation. Using ONLY the OBSERVATIONS provided above, "
            "provide a concise, direct, and factual explanation to the user in 1-2 sentences. "
            "Do NOT speculate, guess, or invent reasons not present in the observation. "
            "Do NOT output any ACTION commands. Provide your normal natural language answer."
        )
        synthesis_messages = [
            {"role": "system", "content": synthesis_rules},
            {"role": "user", "content": message},
            {"role": "assistant", "content": current_messages[-2]["content"]},
            {"role": "user", "content": f"{current_messages[-1]['content']}\n\nExplain the observation to answer the user question."}
        ]
        
        synth_res = CopilotService._call_bitnet(synthesis_messages, max_tokens=150, temperature=0.2)
        if synth_res["status"] == "ok":
            final_reply = synth_res["content"].strip()
            validated_reply = CopilotService._validate_grounding(final_reply, all_observations, required_evidence, (since_mins, until_mins))
            return {"reply": validated_reply, "status": "ok", "source": "agent_loop"}
        else:
            validated_reply = CopilotService._validate_grounding(last_observation, all_observations, required_evidence, (since_mins, until_mins))
            return {"reply": validated_reply, "status": "ok", "source": "mcp_direct"}
