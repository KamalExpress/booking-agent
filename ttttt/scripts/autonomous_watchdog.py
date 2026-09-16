#!/usr/bin/env python3
"""
Autonomous Operational Observer (Watchdog Agent)
=================================================
Closed-loop supervisor implementing the EDR (Explain, Diagnose & Recover) standard:
Sense (Telemetry) -> Diagnose (Anomalies) -> Decide (Policies) -> Act (Self-Healing) -> Verify

Supports both:
1. Native Redis Streams Ingestion (via Consumer Group 'watchdog-group' + XREADGROUP + XACK)
2. WebSocket Live Stream Bridge (fallback transport for remote environments)
"""

import os
import sys
import time
import json
import asyncio
import functools
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

print = functools.partial(print, flush=True)

try:
    import websockets
except ImportError:
    websockets = None

try:
    import redis
except ImportError:
    redis = None


# Terminal ANSI Formatting
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


class WatchdogClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("WATCHDOG_API_KEY", "")

    def _request(self, path: str, data: Optional[bytes] = None, timeout: int = 8) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        headers = {
            "X-Watchdog-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> Optional[Dict[str, Any]]:
        res = self._request("/api/v1/watchdog/status")
        if res and "error" not in res:
            return res
        return None

    def trigger_poll(self, visa_center: Optional[str] = None, unpause: bool = True) -> Optional[Dict[str, Any]]:
        params = []
        if visa_center:
            params.append(f"visa_center={visa_center}")
        if unpause:
            params.append("unpause=true")
        query_str = f"?{'&'.join(params)}" if params else ""
        return self._request(f"/api/v1/watchdog/trigger-poll{query_str}", data=b"{}")

    def reset_queue(self) -> Optional[Dict[str, Any]]:
        return self._request("/api/v1/watchdog/reset-queue", data=b"{}")

    def reset_cooldowns(self) -> Optional[Dict[str, Any]]:
        return self._request("/api/v1/watchdog/reset-cooldowns", data=b"{}")

    def inject_otp(self, task_id: int, otp_code: str) -> Optional[Dict[str, Any]]:
        payload = json.dumps({"task_id": task_id, "otp_code": otp_code}).encode()
        return self._request("/api/v1/watchdog/inject-otp", data=payload)


class AutonomousWatchdogEngine:
    def __init__(self, client: WatchdogClient, auto_heal: bool = True):
        self.client = client
        self.auto_heal = auto_heal
        self.in_flight_tasks: Dict[str, Dict[str, Any]] = {}
        self.seen_log_ids: Set[int] = set()
        self.last_action_times: Dict[str, float] = {}
        self.total_slots_found = 0
        self.total_dispatched = 0
        self.total_confirmed = 0
        self.total_failed = 0
        self.total_auto_healed = 0

    def format_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def print_banner(self, transport_desc: str):
        mode_badge = f"{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} AUTONOMOUS SELF-HEALING ACTIVE {Colors.RESET}" if self.auto_heal else f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} PASSIVE OBSERVATION ONLY {Colors.RESET}"
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}   AUTONOMOUS OPERATIONAL OBSERVER & WATCHDOG (EDR SUPERVISOR){Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f" {Colors.DIM}Target Control Plane:{Colors.RESET} {self.client.base_url}")
        print(f" {Colors.DIM}Event Ingestion:{Colors.RESET}      {transport_desc}")
        print(f" {Colors.DIM}Supervisory Mode:{Colors.RESET}     {mode_badge}")
        print(f" {Colors.DIM}Local Time:{Colors.RESET}           {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Colors.CYAN}{'-'*80}{Colors.RESET}")
        print(f" {Colors.BOLD}Pipeline Stages:{Colors.RESET}")
        print(f"  [S1: MONITOR] -> [S2: SLOTS] -> [S3: QUEUE] -> [S4: BOOKER] -> [S5: OTP] -> [S6: CONFIRM]")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

    def print_system_snapshot(self):
        status = self.client.get_status()
        if not status:
            print(f"[{self.format_time()}] {Colors.YELLOW}[WATCHDOG STATUS] Control plane status endpoint awaiting deployment/unreachable.{Colors.RESET}")
            return

        wrks = status.get("workers", [])
        asms = status.get("assignments", [])
        q_sum = status.get("queue_summary", {}).get("counts", {})
        q_items = status.get("queue_summary", {}).get("items", [])
        acc_sum = status.get("accounts_summary", {})
        recent_logs = status.get("recent_logs", [])

        online_monitors = sum(1 for w in wrks if (w.get("can_scrape") or w.get("can_monitor")) and w.get("is_online"))
        online_bookers = sum(1 for w in wrks if w.get("can_book") and w.get("is_online"))

        print(f"\n{Colors.BOLD}{Colors.WHITE}--- LIVE SYSTEM TOPOLOGY SNAPSHOT ---{Colors.RESET}")
        print(f" {Colors.BOLD}Workers:{Colors.RESET}     Monitors: {Colors.GREEN if online_monitors else Colors.RED}{online_monitors} online{Colors.RESET} | "
              f"Bookers: {Colors.GREEN if online_bookers else Colors.RED}{online_bookers} online{Colors.RESET} (Total: {len(wrks)})")

        print(f" {Colors.BOLD}Monitoring:{Colors.RESET}  {len(asms)} Active Assignment(s)")
        for a in asms:
            due_str = f"{Colors.GREEN}{Colors.BOLD}POLLING DUE NOW{Colors.RESET}" if a.get("is_due_for_polling") else f"Next poll in {a.get('next_due_seconds')}s"
            print(f"   Center {a.get('visa_center')}: Status={a.get('status')} | Interval={a.get('polling_interval')}s | {due_str}")

        print(f" {Colors.BOLD}Waitlist:{Colors.RESET}    PENDING/WAITING: {Colors.YELLOW}{q_sum.get('PENDING', 0)}{Colors.RESET} | "
              f"DISPATCHED: {Colors.CYAN}{q_sum.get('DISPATCHED', 0)}{Colors.RESET} | "
              f"BOOKED: {Colors.GREEN}{q_sum.get('BOOKED', 0)}{Colors.RESET} | "
              f"FAILED: {Colors.RED}{q_sum.get('FAILED', 0)}{Colors.RESET}")

        if q_items:
            print(f" {Colors.DIM}Queue Sample:{Colors.RESET}")
            for item in q_items[:4]:
                print(f"   - #{item.get('id')} {item.get('applicant_name')} (VAC {item.get('visa_center')}) -> State: {item.get('status')}")

        print(f" {Colors.BOLD}Accounts:{Colors.RESET}    READY: {Colors.GREEN}{acc_sum.get('READY', 0)}{Colors.RESET} | "
              f"LEASED: {Colors.BLUE}{acc_sum.get('LEASED', 0)}{Colors.RESET} | "
              f"COOLDOWN: {Colors.YELLOW}{acc_sum.get('COOLDOWN', 0)}{Colors.RESET}")

        if recent_logs:
            print(f"\n{Colors.BOLD}{Colors.WHITE}--- RECENT LOGS CATCHUP ---{Colors.RESET}")
            for lg in reversed(recent_logs[:5]):
                self.seen_log_ids.add(lg.get("id"))
                ts = (lg.get("timestamp") or "")[11:19]
                print(f"[{ts}] {Colors.DIM}[{lg.get('event_type')}]{Colors.RESET} ({lg.get('worker_id')}): {json.dumps(lg.get('payload'))[:110]}")

        print(f"{Colors.WHITE}{'-'*50}{Colors.RESET}\n")

    def process_event(self, event: Dict[str, Any]):
        event_type = event.get("event_type", "UNKNOWN")
        worker_id = event.get("worker_id", "system")
        payload = event.get("payload") or {}
        timestamp = event.get("timestamp") or self.format_time()
        time_str = timestamp[11:19] if "T" in timestamp else self.format_time()

        if event_type == "QUEUE_ENQUEUED":
            app_id = payload.get("applicant_id", "?")
            name = payload.get("applicant_name", "Applicant")
            vac = payload.get("visa_center", "?")
            print(f"[{time_str}] {Colors.CYAN}{Colors.BOLD}[S3: QUEUE ENQUEUED]{Colors.RESET} "
                  f"Applicant #{app_id} ({name}) enqueued into Waitlist for Center {vac}.")

        elif event_type == "QUEUE_REMOVED":
            app_id = payload.get("applicant_id", "?")
            qid = payload.get("queue_id", "?")
            print(f"[{time_str}] {Colors.DIM}[S3: QUEUE REMOVED]{Colors.RESET} "
                  f"Entry #{qid} (Applicant #{app_id}) removed from Waitlist.")

        elif event_type == "QUEUE_RESET":
            app_id = payload.get("applicant_id", "?")
            qid = payload.get("queue_id", "?")
            print(f"[{time_str}] {Colors.YELLOW}[S3: QUEUE RESET]{Colors.RESET} "
                  f"Entry #{qid} (Applicant #{app_id}) reset to WAITING/PENDING.")

        elif event_type == "ASSIGNMENT_RESCHEDULED":
            asm_id = payload.get("assignment_id", "?")
            vac = payload.get("visa_center", "?")
            print(f"[{time_str}] {Colors.GREEN}{Colors.BOLD}[S1: ASSIGNMENT RESCHEDULED]{Colors.RESET} "
                  f"Assignment #{asm_id} (Center {vac}) rescheduled for IMMEDIATE polling.")

        elif event_type == "SLOT_FOUND":
            self.total_slots_found += 1
            vac = payload.get("visa_center", "?")
            date = payload.get("date", "Unknown")
            slots = payload.get("slots", [])
            print(f"[{time_str}] {Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [S2: SLOTS DISCOVERED] {Colors.RESET} "
                  f"{Colors.GREEN}{Colors.BOLD}{len(slots)} Slot(s) open at Center {vac} on {date}!{Colors.RESET} "
                  f"{Colors.DIM}(Worker: {worker_id}){Colors.RESET}")

        elif event_type == "NO_SLOTS_FOUND":
            vac = payload.get("visa_center", "?")
            print(f"[{time_str}] {Colors.DIM}[S1: MONITOR]{Colors.RESET} Worker '{worker_id}' checked Center {vac}: No open slots. (Healthy)")

        elif event_type == "BOOKING_DISPATCHED":
            self.total_dispatched += 1
            task_id = str(payload.get("task_id", "?"))
            app_id = payload.get("applicant_id", "?")
            vac = payload.get("visa_center", "?")
            date = payload.get("target_date", "?")
            time_slot = payload.get("target_time", "?")

            self.in_flight_tasks[task_id] = {
                "stage": 3,
                "start_time": time.time(),
                "applicant_id": app_id,
                "center": vac,
                "slot": f"{date} @ {time_slot}"
            }
            print(f"[{time_str}] {Colors.CYAN}{Colors.BOLD}[S3: QUEUE DISPATCH]{Colors.RESET} "
                  f"Applicant #{app_id} matched -> {Colors.BOLD}BookingTask #{task_id}{Colors.RESET} "
                  f"({date} @ {time_slot} | Center {vac})")

        elif event_type == "BOOKING_CLAIMED":
            task_id = str(payload.get("task_id", "?"))
            acc = payload.get("account", "Account")
            if task_id in self.in_flight_tasks:
                self.in_flight_tasks[task_id]["stage"] = 4
                self.in_flight_tasks[task_id]["worker"] = worker_id
            else:
                self.in_flight_tasks[task_id] = {"stage": 4, "start_time": time.time(), "worker": worker_id}

            print(f"[{time_str}] {Colors.BLUE}{Colors.BOLD}[S4: BOOKER CLAIM]{Colors.RESET} "
                  f"BookingTask #{task_id} CLAIMED by {Colors.BOLD}{worker_id}{Colors.RESET} (Account: {acc})")

        elif event_type in ["OTP_RECEIVED", "OTP_INTERCEPTED"]:
            otp = payload.get("extracted_otp") or payload.get("otp_code") or "12345"
            print(f"[{time_str}] {Colors.MAGENTA}{Colors.BOLD}[S5: OTP INTERCEPTED]{Colors.RESET} "
                  f"Verification Code captured: {Colors.BOLD}{otp}{Colors.RESET} -> Injected into booking form")

        elif event_type == "BOOKING_SUCCESS":
            self.total_confirmed += 1
            task_id = str(payload.get("task_id", "?"))
            ref = payload.get("reference_number", "N/A")
            app_id = payload.get("applicant_id", "?")
            vac = payload.get("visa_center", "?")
            duration = "?"
            if task_id in self.in_flight_tasks:
                duration = f"{time.time() - self.in_flight_tasks[task_id]['start_time']:.1f}s"
                del self.in_flight_tasks[task_id]

            print(f"\n[{time_str}] {Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [S6: CONFIRMATION SUCCESS] {Colors.RESET} "
                  f"{Colors.GREEN}{Colors.BOLD}Visa Appointment SECURED for Applicant #{app_id}!{Colors.RESET}\n"
                  f"       {Colors.BOLD}Reference Code:{Colors.RESET} {Colors.YELLOW}{ref}{Colors.RESET} | "
                  f"{Colors.BOLD}Center:{Colors.RESET} {vac} | {Colors.BOLD}Time:{Colors.RESET} {duration} | "
                  f"{Colors.BOLD}Queue State:{Colors.RESET} {Colors.GREEN}BOOKED{Colors.RESET}\n")

        elif event_type in ["BOOKING_FAILED", "BOOKING_ALREADY_EXISTS"]:
            self.total_failed += 1
            task_id = str(payload.get("task_id", "?"))
            reason = payload.get("reason", "Failure")
            if task_id in self.in_flight_tasks:
                del self.in_flight_tasks[task_id]

            if "ALREADY" in str(reason).upper() or event_type == "BOOKING_ALREADY_EXISTS":
                print(f"[{time_str}] {Colors.YELLOW}{Colors.BOLD}[EDGE CASE: ALREADY BOOKED]{Colors.RESET} "
                      f"Task #{task_id}: Active booking exists on portal. Queue state -> {Colors.YELLOW}CANCELLED{Colors.RESET}.")
            else:
                print(f"[{time_str}] {Colors.RED}{Colors.BOLD}[BOOKING FAILED]{Colors.RESET} "
                  f"Task #{task_id} failed: {reason}. (Worker: {worker_id})")

        elif event_type in ["WAF_CHALLENGE", "PROXY_BANNED", "LOGIN_FAILED"]:
            reason = payload.get("reason", "")
            print(f"[{time_str}] {Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} [SECURITY BLOCK: {event_type}] {Colors.RESET} "
                  f"Worker {worker_id} encountered: {reason}\n"
                  f"       {Colors.YELLOW}-> Watchdog Recommendation: Verify proxy health or browser persona.{Colors.RESET}")

        elif event_type == "LEASE_RESULT":
            st = payload.get("status", "COMPLETED")
            reason = payload.get("reason", "")
            if st == "COMPLETED":
                print(f"[{time_str}] {Colors.GREEN}[S1: LEASE CYCLE COMPLETED]{Colors.RESET} "
                      f"Worker '{worker_id}' finished monitoring cycle successfully.")
            else:
                print(f"[{time_str}] {Colors.RED}[LEASE FAILED]{Colors.RESET} "
                      f"Worker '{worker_id}' lease finished with failure: {reason or 'Unknown error'}")

        elif event_type == "LOGIN_SUCCESS":
            user = payload.get("username", "account")
            print(f"[{time_str}] {Colors.GREEN}[S1: AUTH SUCCESS]{Colors.RESET} "
                  f"Worker '{worker_id}' authenticated to GVC portal as '{user}'.")

        elif event_type == "PUSH_SENT":
            title = payload.get("title", "Notification")
            body = payload.get("body", "")
            sc = payload.get("success_count", 1)
            print(f"[{time_str}] {Colors.CYAN}{Colors.BOLD}[PUSH DISPATCH]{Colors.RESET} "
                  f"Broadcasted '{title}': \"{body}\" (Delivered to {sc} subscriber(s))")

        elif event_type == "LEASE_CANCELLED":
            reason = payload.get("reason", "Cancelled")
            print(f"[{time_str}] {Colors.YELLOW}[LEASE AUTO-PAUSED]{Colors.RESET} "
                  f"Monitoring lease for '{worker_id}' paused (Reason: {reason}).")

        elif event_type == "NO_ASSIGNMENT":
            print(f"[{time_str}] {Colors.DIM}[SCHEDULER: IDLE]{Colors.RESET} "
                  f"No monitoring or booking tasks available for '{worker_id}'.")

        elif event_type in ["CAPTCHA_SOLVING", "CAPTCHA_SOLVED"]:
            status_c = Colors.GREEN if "SOLVED" in event_type else Colors.YELLOW
            print(f"[{time_str}] {status_c}[CAPTCHA {event_type}]{Colors.RESET} "
                  f"Worker '{worker_id}' captcha status: {payload.get('status', 'processing')}")

        elif event_type in ["LEASE_EXPIRED", "LEASE_ABANDONED"]:
            print(f"[{time_str}] {Colors.YELLOW}[LEASE {event_type}]{Colors.RESET} "
                  f"Orphan lease reclaimed for worker {worker_id}. Task auto-recovered to PENDING.")

        else:
            print(f"[{time_str}] {Colors.DIM}[EVENT: {event_type}]{Colors.RESET} ({worker_id}) {json.dumps(payload)[:100]}")

    def execute_rate_limited_action(self, action_name: str, fn, cooldown_seconds: int = 20) -> Optional[Dict[str, Any]]:
        now = time.time()
        last = self.last_action_times.get(action_name, 0)
        if now - last < cooldown_seconds:
            return None
        self.last_action_times[action_name] = now
        res = fn()
        return res

    def evaluate_and_heal(self):
        """Diagnose anomalies across the pipeline and execute closed-loop self-healing."""
        now = time.time()

        # 1. In-flight task stall detection
        for task_id, task in list(self.in_flight_tasks.items()):
            elapsed = now - task["start_time"]
            stage = task["stage"]
            if stage == 3 and elapsed > 20:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[DIAGNOSE: STAGE 3 STALL]{Colors.RESET} "
                      f"Task #{task_id} DISPATCHED for {elapsed:.0f}s without Booker claim.")
                if self.auto_heal:
                    res = self.execute_rate_limited_action("reset_queue", self.client.reset_queue, cooldown_seconds=25)
                    if res and res.get("status") == "ok":
                        self.total_auto_healed += 1
                        print(f"[{self.format_time()}] {Colors.BG_MAGENTA}{Colors.WHITE}{Colors.BOLD} [AUTONOMOUS RECOVERY] {Colors.RESET} "
                              f"{Colors.GREEN}Auto-reset stuck queue entries back to WAITING.{Colors.RESET}")
                        if task_id in self.in_flight_tasks:
                            del self.in_flight_tasks[task_id]

            elif stage == 4 and elapsed > 45:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[DIAGNOSE: STAGE 4-5 STALL]{Colors.RESET} "
                      f"Task #{task_id} in-flight with {task.get('worker')} for {elapsed:.0f}s without progress.")

        # 2. Status evaluation & catchup
        status = self.client.get_status()
        if status:
            wrks = status.get("workers", [])
            asms = status.get("assignments", [])
            q_sum = status.get("queue_summary", {}).get("counts", {})
            recent_logs = status.get("recent_logs", [])
            acc_sum = status.get("accounts_summary", {})

            # Catch up on any DB logs not received
            for lg in reversed(recent_logs):
                lid = lg.get("id")
                if lid and lid not in self.seen_log_ids:
                    self.seen_log_ids.add(lid)
                    ts = (lg.get("timestamp") or "")[11:19]
                    print(f"[{ts}] {Colors.CYAN}[PROACTIVE CATCHUP]{Colors.RESET} [{lg.get('event_type')}] ({lg.get('worker_id')}): {json.dumps(lg.get('payload'))[:100]}")

            online_monitors = sum(1 for w in wrks if (w.get("can_scrape") or w.get("can_monitor")) and w.get("is_online"))
            online_bookers = sum(1 for w in wrks if w.get("can_book") and w.get("is_online"))
            pending_q = q_sum.get("PENDING", 0)
            dispatched_q = q_sum.get("DISPATCHED", 0)

            # Anomaly 1: Fleet Starvation
            if (pending_q > 0 or dispatched_q > 0) and online_monitors == 0 and online_bookers == 0:
                print(f"[{self.format_time()}] {Colors.RED}{Colors.BOLD}[DIAGNOSE: FLEET STARVATION]{Colors.RESET} "
                      f"Waitlist has {pending_q} WAITING / {dispatched_q} DISPATCHED item(s), but {Colors.RED}0 Workers are Online{Colors.RESET}!\n"
                      f"       {Colors.YELLOW}-> Recommendation: Start operator/booker worker containers.{Colors.RESET}")

            # Anomaly 2: No Booker Available when tasks or slots exist
            elif (dispatched_q > 0 or self.total_slots_found > 0) and online_bookers == 0:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[DIAGNOSE: NO BOOKER ONLINE]{Colors.RESET} "
                      f"Discovered slots available, but {Colors.YELLOW}0 Booker workers are online{Colors.RESET} (`can_book=True`).\n"
                      f"       {Colors.YELLOW}-> Recommendation: Launch headless booker (`python headless_booker.py`).{Colors.RESET}")

            # Anomaly 3: Monitoring Paused while Queue is Waiting
            active_asms = [a for a in asms if a.get("status") == "Active"]
            paused_asms = [a for a in asms if a.get("status") == "Paused"]
            if len(asms) > 0 and len(active_asms) == 0 and len(paused_asms) > 0 and pending_q > 0:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[DIAGNOSE: MONITORING HALTED]{Colors.RESET} "
                      f"All {len(paused_asms)} monitoring assignment(s) are PAUSED while {pending_q} applicant(s) are WAITING in queue.\n"
                      f"       {Colors.DIM}-> Root Cause: Monitoring auto-paused after recent slot discovery.{Colors.RESET}\n"
                      f"       {Colors.YELLOW}-> Recommendation: Unpause assignments and trigger active monitoring.{Colors.RESET}")
                if self.auto_heal:
                    res = self.execute_rate_limited_action("unpause_poll", lambda: self.client.trigger_poll(unpause=True), cooldown_seconds=30)
                    if res and res.get("status") == "ok":
                        self.total_auto_healed += 1
                        print(f"[{self.format_time()}] {Colors.BG_MAGENTA}{Colors.WHITE}{Colors.BOLD} [AUTONOMOUS RECOVERY] {Colors.RESET} "
                              f"{Colors.GREEN}Auto-unpaused and triggered active polling for {len(paused_asms)} assignment(s).{Colors.RESET}")

            # Anomaly 4: Account Deadlock
            ready_accs = acc_sum.get("READY", 0)
            cooldown_accs = acc_sum.get("COOLDOWN", 0)
            if ready_accs == 0 and cooldown_accs > 0 and (pending_q > 0 or dispatched_q > 0):
                print(f"[{self.format_time()}] {Colors.YELLOW}[DIAGNOSE: RESOURCE LOCK DEADLOCK]{Colors.RESET} "
                      f"0 portal accounts READY ({cooldown_accs} in COOLDOWN).\n"
                      f"       {Colors.YELLOW}-> Recommendation: Reset account cooldowns.{Colors.RESET}")
                if self.auto_heal:
                    res = self.execute_rate_limited_action("reset_cooldowns", self.client.reset_cooldowns, cooldown_seconds=30)
                    if res and res.get("status") == "ok":
                        self.total_auto_healed += 1
                        print(f"[{self.format_time()}] {Colors.BG_MAGENTA}{Colors.WHITE}{Colors.BOLD} [AUTONOMOUS RECOVERY] {Colors.RESET} "
                              f"{Colors.GREEN}Auto-cleared account/proxy cooldown locks.{Colors.RESET}")

            # Anomaly 5: Booking Task Lease Deadlock (Holding Accounts)
            b_tasks = status.get("booking_tasks", [])
            stuck_tasks = [t for t in b_tasks if t.get("status") in ["PENDING", "CLAIMED"]]
            if ready_accs == 0 and len(stuck_tasks) > 0:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[DIAGNOSE: BOOKING TASK LEASE DEADLOCK]{Colors.RESET} "
                      f"0 accounts are READY (all {acc_sum.get('LEASED', 0)} LEASED). Task(s) #{[t['id'] for t in stuck_tasks]} holding account leases, blocking new dispatches.\n"
                      f"       {Colors.YELLOW}-> Recommendation: Release stuck booking leases and reset queue entries to PENDING.{Colors.RESET}")
                if self.auto_heal:
                    res = self.execute_rate_limited_action("reset_stuck_tasks", self.client.reset_queue, cooldown_seconds=20)
                    if res and res.get("status") == "ok":
                        self.total_auto_healed += 1
                        print(f"[{self.format_time()}] {Colors.BG_MAGENTA}{Colors.WHITE}{Colors.BOLD} [AUTONOMOUS RECOVERY] {Colors.RESET} "
                              f"{Colors.GREEN}Auto-released stuck booking leases and reset queue entries to PENDING.{Colors.RESET}")

            # Pulse line
            active_next_poll = min([a.get("next_due_seconds", 999) for a in active_asms], default=None)
            if active_next_poll is not None:
                poll_text = f"Next poll in {active_next_poll}s" if active_next_poll > 0 else f"{Colors.GREEN}Polling due NOW{Colors.RESET}"
            elif paused_asms:
                poll_text = f"{Colors.YELLOW}Monitoring PAUSED{Colors.RESET}"
            else:
                poll_text = "No assignments"

            heal_badge = f" | {Colors.MAGENTA}Heals: {self.total_auto_healed}{Colors.RESET}" if self.auto_heal else ""
            print(f"[{self.format_time()}] {Colors.DIM}[WATCHDOG PULSE]{Colors.RESET} "
                  f"Workers: {online_monitors} Monitors / {online_bookers} Bookers | "
                  f"Queue: {pending_q} WAITING / {dispatched_q} DISPATCHED | {poll_text}{heal_badge}")
        else:
            print(f"[{self.format_time()}] {Colors.DIM}[WATCHDOG PULSE]{Colors.RESET} "
                  f"Stream active on {self.client.base_url} | Monitoring live worker events...")


async def start_redis_stream_supervisor(redis_url: str, saas_url: str, api_key: str, auto_heal: bool):
    """Direct high-performance ingestion via Redis Streams Consumer Group."""
    client = WatchdogClient(saas_url, api_key)
    engine = AutonomousWatchdogEngine(client, auto_heal=auto_heal)

    engine.print_banner(f"Redis Streams (Consumer Group: 'watchdog-group' @ {redis_url.split('@')[-1]})")
    engine.print_system_snapshot()

    r = redis.Redis.from_url(redis_url, decode_responses=True)
    topic = "events:pipeline"
    group = "watchdog-group"
    consumer_id = f"watchdog-{os.getpid()}"

    try:
        r.xgroup_create(topic, group, id="$", mkstream=True)
    except Exception:
        pass

    async def evaluation_loop():
        while True:
            await asyncio.sleep(7)
            engine.evaluate_and_heal()

    asyncio.create_task(evaluation_loop())

    print(f"[{engine.format_time()}] {Colors.GREEN}{Colors.BOLD}CONNECTED to Redis Stream! Autonomous Watchdog is actively supervising.{Colors.RESET}\n")
    while True:
        try:
            entries = await asyncio.to_thread(
                r.xreadgroup,
                groupname=group,
                consumername=consumer_id,
                streams={topic: ">"},
                count=10,
                block=2000
            )
            if entries:
                ack_ids = []
                for stream_name, messages in entries:
                    for msg_id, fields in messages:
                        ack_ids.append(msg_id)
                        payload_raw = fields.get("payload", "{}")
                        try:
                            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
                        except Exception:
                            payload = {"raw": payload_raw}

                        engine.process_event({
                            "event_id": fields.get("event_id"),
                            "event_type": fields.get("event_type"),
                            "source": fields.get("source"),
                            "worker_id": fields.get("worker_id"),
                            "payload": payload,
                            "timestamp": fields.get("timestamp")
                        })
                if ack_ids:
                    await asyncio.to_thread(r.xack, topic, group, *ack_ids)
        except Exception as e:
            print(f"[{engine.format_time()}] {Colors.YELLOW}Redis Stream read error ({e}). Retrying in 2s...{Colors.RESET}")
            await asyncio.sleep(2)


async def start_ws_supervisor(saas_url: str, api_key: str, auto_heal: bool):
    """Fallback transport ingestion via WebSocket Live Bridge."""
    client = WatchdogClient(saas_url, api_key)
    engine = AutonomousWatchdogEngine(client, auto_heal=auto_heal)

    base_url = saas_url.rstrip("/")
    ws_protocol = "wss" if base_url.startswith("https") else "ws"
    host = base_url.split("://")[1]
    ws_url = f"{ws_protocol}://{host}/ws/live-logs"

    engine.print_banner(f"WebSocket Live Bridge ({ws_url})")
    engine.print_system_snapshot()

    async def evaluation_loop():
        while True:
            await asyncio.sleep(7)
            engine.evaluate_and_heal()

    asyncio.create_task(evaluation_loop())

    retry_delay = 3
    headers = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")]
    while True:
        try:
            print(f"[{engine.format_time()}] Connecting to SaaS WebSocket stream...")
            try:
                conn = websockets.connect(ws_url, additional_headers=headers, ping_interval=20, ping_timeout=20)
            except TypeError:
                conn = websockets.connect(ws_url, extra_headers=dict(headers), ping_interval=20, ping_timeout=20)

            async with conn as ws:
                print(f"[{engine.format_time()}] {Colors.GREEN}{Colors.BOLD}CONNECTED! Autonomous Watchdog is supervising the live pipeline.{Colors.RESET}\n")
                retry_delay = 3
                while True:
                    message_raw = await ws.recv()
                    try:
                        event = json.loads(message_raw)
                        engine.process_event(event)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[{engine.format_time()}] {Colors.YELLOW}WebSocket stream disconnected ({e}). Retrying in {retry_delay}s...{Colors.RESET}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 15)


def main():
    parser = argparse.ArgumentParser(description="Autonomous Operational Observer & Watchdog for Booking Automation")
    parser.add_argument("--saas-url", default=os.getenv("SAAS_BASE_URL", "https://keagent.alamiaconnect.com"),
                        help="Base URL of the SaaS control plane (default: https://keagent.alamiaconnect.com)")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL"),
                        help="Direct Redis Streams URL (e.g. redis://localhost:6379/0)")
    parser.add_argument("--api-key", default=os.getenv("WATCHDOG_API_KEY", ""),
                        help="API key for watchdog status and recovery endpoints")
    parser.add_argument("--no-heal", action="store_true",
                        help="Disable automated self-healing actions (passive observation only)")
    parser.add_argument("--snapshot", action="store_true",
                        help="Print current system topology snapshot and exit")
    parser.add_argument("--trigger-poll", action="store_true",
                        help="Immediately surge monitoring assignments to poll right away")
    parser.add_argument("--reset-queue", action="store_true",
                        help="Immediately self-heal and reset stuck queue entries to WAITING")
    parser.add_argument("--reset-cooldowns", action="store_true",
                        help="Immediately reset all portal accounts and proxies in COOLDOWN")
    args = parser.parse_args()

    client = WatchdogClient(args.saas_url, args.api_key)
    engine = AutonomousWatchdogEngine(client, auto_heal=not args.no_heal)

    if args.snapshot:
        engine.print_system_snapshot()
        return

    if args.trigger_poll:
        res = client.trigger_poll()
        print("Trigger Poll Result:", res)
        return

    if args.reset_queue:
        res = client.reset_queue()
        print("Reset Queue Result:", res)
        return

    if args.reset_cooldowns:
        res = client.reset_cooldowns()
        print("Reset Cooldowns Result:", res)
        return

    try:
        if args.redis_url and redis:
            asyncio.run(start_redis_stream_supervisor(args.redis_url, args.saas_url, args.api_key, auto_heal=not args.no_heal))
        else:
            asyncio.run(start_ws_supervisor(args.saas_url, args.api_key, auto_heal=not args.no_heal))
    except KeyboardInterrupt:
        print("\nWatchdog supervisor stopped by user.")


if __name__ == "__main__":
    main()
