import os
import requests
import json
import re
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List
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
    @staticmethod
    async def list_tools() -> List[Dict[str, Any]]:
        """MCP tools/list: discover registered tools and their JSON schemas from FastMCP."""
        try:
            from mcp_server import mcp
            raw_tools = await mcp.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": getattr(t, "inputSchema", {})
                }
                for t in raw_tools
            ]
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

    @staticmethod
    async def call_tool(name: str, arguments: Dict[str, Any]) -> str:
        """MCP tools/call: execute a tool through the FastMCP server dispatch pipeline."""
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
                slots_summary = TravelOSMCPClient.call_tool_sync("get_available_slots", {"visa_center": visa_center, "limit": 10})
                return {"type": "text", "content": slots_summary}

            elif action in ["proxy_health", "proxies"]:
                proxy_summary = TravelOSMCPClient.call_tool_sync("get_proxy_health", {})
                return {"type": "text", "content": proxy_summary}

            elif action in ["unfreeze", "unlease"]:
                rtype = params.get("resource_type", "account") if params else "account"
                rid = params.get("resource_id", 0) if params else 0
                res = TravelOSMCPClient.call_tool_sync("unlease_resource", {"resource_type": rtype, "resource_id": rid})
                return {"type": "text", "content": res}
                
            elif action in ["maintenance", "orphan_cleanup"]:
                res = TravelOSMCPClient.call_tool_sync("trigger_maintenance_cycle", {})
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
                            
        # Map common aliases to canonical FastMCP tool names
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
        
        # Heuristic argument normalization
        if "worker" in canonical_tool and "worker_id" not in args:
            for k, v in args.items():
                if "worker" in str(k).lower():
                    args["worker_id"] = str(k)
                    break
                elif "worker" in str(v).lower():
                    args["worker_id"] = str(v)
                    break
                    
        return {"tool": canonical_tool, "args": args}

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
                    "reply": "🔒 Alamia Copilot Pro is an enterprise add-on for this agency. Please contact your administrator to upgrade your plan.",
                    "status": "upgrade_required"
                }

        lower_msg = message.strip().lower()

        # 2. Tier 1: Deterministic Fast Paths (0 LLM Tokens, 0.01s Latency via MCP)
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

        # 3. Tier 2: MCP Discovery (tools/list) & Structured Agent Loop
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        # Step 3.1: Stable System Instructions (Owned by TravelOS Copilot)
        system_rules = (
            "You are Alamia TravelOS Copilot, the operational assistant for TravelOS.\n"
            "Answer factually and concisely (under 2 sentences).\n"
            "If operational data is needed, reply ONLY with:\n"
            "ACTION: <tool_name>(<arguments>)\n"
            "When an OBSERVATION is given, base your answer strictly on it."
        )
        
        # Step 3.2: MCP Tool Discovery via FastMCP tools/list
        mcp_tools = TravelOSMCPClient.list_tools_sync()
        
        # Filter relevant tools based on query to avoid token overload
        q = message.lower()
        selected_tools = []
        for t in mcp_tools:
            t_name = t["name"].lower()
            if any(w in q for w in ["worker", "fail", "stuck", "node"]) and "worker" in t_name:
                selected_tools.append(t)
            elif any(s in q for s in ["slot", "appointment", "date"]) and "slot" in t_name:
                selected_tools.append(t)
            elif any(p in q for p in ["proxy", "ip"]) and "proxy" in t_name:
                selected_tools.append(t)
            elif any(h in q for h in ["health", "system", "portal"]) and ("health" in t_name or "portal" in t_name):
                selected_tools.append(t)
                
        if not selected_tools:
            # Default core subset from MCP tools/list
            selected_tools = [t for t in mcp_tools if t["name"] in ["get_workers", "get_available_slots", "get_proxy_health", "get_portal_health_summary"]]
            
        selected_tools = selected_tools[:4]
        
        tool_lines = ["Available MCP Operational Tools:"]
        for t in selected_tools:
            params_str = json.dumps(t["inputSchema"].get("properties", {}))
            tool_lines.append(f"- {t['name']}({params_str}): {t['description']}")
        tool_sigs = "\n".join(tool_lines)
        
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
            
        # Step 3.4: Invoke MCP tools/call via FastMCP Server
        tool_name = tool_call["tool"]
        tool_args = tool_call["args"]
        print(f"[Copilot MCP Client] Invoking MCP tools/call: {tool_name}({tool_args})")
        
        observation = TravelOSMCPClient.call_tool_sync(tool_name, tool_args)
        print(f"[Copilot MCP Client] FastMCP Observation: {observation[:120]}...")
        
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
            if final_reply.startswith("ACTION:"):
                return {"reply": f"Based on live FastMCP telemetry: {observation}", "status": "ok", "source": "mcp_direct"}
            return {"reply": final_reply, "status": "ok", "source": "agent_loop"}
        else:
            return {"reply": f"{observation}", "status": "ok", "source": "mcp_direct"}
