#!/usr/bin/env python3
"""
Real-Time System Watchdog & Observer Tool
=========================================
Monitors the end-to-end booking automation pipeline across all 6 stages:
  [S1: MONITOR] -> [S2: SLOTS] -> [S3: QUEUE] -> [S4: BOOKER] -> [S5: OTP] -> [S6: CONFIRM]

Features:
- Token-based API access (no manual browser login needed).
- Real-time WebSocket event streaming.
- Live pipeline state diagnostics & stall detection.
- Self-healing trigger controls (trigger-poll, reset-queue, reset-cooldowns).

Usage:
  python scripts/observe_system.py --saas-url https://keagent.alamiaconnect.com
  python scripts/observe_system.py --saas-url https://keagent.alamiaconnect.com --api-key 51129693340
"""

import sys
import os
import json
import time
import asyncio
import argparse
import functools
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional

print = functools.partial(print, flush=True)

try:
    import websockets
except ImportError:
    print("Installing 'websockets' dependency for live log streaming...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

# ANSI Colors for Terminal Output
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


class WatchdogClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def get_status(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/watchdog/status"
        req = urllib.request.Request(url, headers={
            "X-Watchdog-Key": self.api_key,
            "User-Agent": "WatchdogObserver/2.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None

    def trigger_poll(self, visa_center: Optional[str] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/watchdog/trigger-poll"
        if visa_center:
            url += f"?visa_center={visa_center}"
        req = urllib.request.Request(url, data=b"", headers={
            "X-Watchdog-Key": self.api_key,
            "User-Agent": "WatchdogObserver/2.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None

    def reset_queue(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/watchdog/reset-queue"
        req = urllib.request.Request(url, data=b"", headers={
            "X-Watchdog-Key": self.api_key,
            "User-Agent": "WatchdogObserver/2.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None


class PipelineTracker:
    def __init__(self, client: WatchdogClient):
        self.client = client
        self.in_flight_tasks: Dict[str, Dict[str, Any]] = {}
        self.total_slots_found = 0
        self.total_dispatched = 0
        self.total_confirmed = 0
        self.total_failed = 0

    def print_banner(self, saas_url: str, ws_url: str):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}   ALAMIA AUTOMATION - LIVE PIPELINE OBSERVER & WATCHDOG{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f" {Colors.DIM}Target SaaS URL:{Colors.RESET} {saas_url}")
        print(f" {Colors.DIM}WebSocket Stream:{Colors.RESET} {ws_url}")
        print(f" {Colors.DIM}Local Time:{Colors.RESET}       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Colors.CYAN}{'-'*80}{Colors.RESET}")
        print(f" {Colors.BOLD}Pipeline Stages:{Colors.RESET}")
        print(f"  [S1: MONITOR] -> [S2: SLOTS] -> [S3: QUEUE] -> [S4: BOOKER] -> [S5: OTP] -> [S6: CONFIRM]")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

    def print_system_snapshot(self):
        status = self.client.get_status()
        if not status:
            print(f"[{self.format_time()}] {Colors.DIM}[SNAPSHOT] Status API endpoint initializing...{Colors.RESET}")
            return

        asms = status.get("assignments", [])
        wrks = status.get("workers", [])
        q_sum = status.get("queue_summary", {}).get("counts", {})
        acc_sum = status.get("accounts_summary", {})

        print(f"\n{Colors.BOLD}{Colors.WHITE}--- LIVE SYSTEM TOPOLOGY SNAPSHOT ---{Colors.RESET}")
        
        # Workers
        online_scrapers = sum(1 for w in wrks if w.get("can_scrape") and w.get("is_online"))
        online_bookers = sum(1 for w in wrks if w.get("can_book") and w.get("is_online"))
        print(f" {Colors.BOLD}Workers:{Colors.RESET}     Scrapers: {Colors.GREEN}{online_scrapers} online{Colors.RESET} | "
              f"Bookers: {Colors.GREEN}{online_bookers} online{Colors.RESET} (Total: {len(wrks)})")

        # Assignments
        print(f" {Colors.BOLD}Monitoring:{Colors.RESET}  {len(asms)} Active Assignment(s)")
        for a in asms:
            due_str = f"{Colors.GREEN}POLLING DUE NOW{Colors.RESET}" if a.get("is_due_for_polling") else f"Next poll in {a.get('next_due_seconds')}s"
            print(f"   Center {a.get('visa_center')}: Status={a.get('status')} | Interval={a.get('polling_interval')}s | {due_str}")

        # Queue
        print(f" {Colors.BOLD}Waitlist:{Colors.RESET}    PENDING: {Colors.YELLOW}{q_sum.get('PENDING', 0)}{Colors.RESET} | "
              f"DISPATCHED: {Colors.CYAN}{q_sum.get('DISPATCHED', 0)}{Colors.RESET} | "
              f"BOOKED: {Colors.GREEN}{q_sum.get('BOOKED', 0)}{Colors.RESET} | "
              f"FAILED: {Colors.RED}{q_sum.get('FAILED', 0)}{Colors.RESET}")

        # Accounts
        print(f" {Colors.BOLD}Accounts:{Colors.RESET}    READY: {Colors.GREEN}{acc_sum.get('READY', 0)}{Colors.RESET} | "
              f"LEASED: {Colors.BLUE}{acc_sum.get('LEASED', 0)}{Colors.RESET} | "
              f"COOLDOWN: {Colors.YELLOW}{acc_sum.get('COOLDOWN', 0)}{Colors.RESET}")
        print(f"{Colors.WHITE}{'-'*45}{Colors.RESET}\n")

    def format_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def process_event(self, event: Dict[str, Any]):
        event_type = event.get("event_type", "UNKNOWN")
        worker_id = event.get("worker_id", "system")
        payload = event.get("payload") or {}
        timestamp = event.get("timestamp") or self.format_time()
        time_str = timestamp[11:19] if "T" in timestamp else self.format_time()

        if event_type == "SLOT_FOUND":
            self.handle_slot_found(time_str, worker_id, payload)
        elif event_type == "NO_SLOTS_FOUND":
            self.handle_no_slots(time_str, worker_id, payload)
        elif event_type == "BOOKING_DISPATCHED":
            self.handle_dispatched(time_str, payload)
        elif event_type == "BOOKING_CLAIMED":
            self.handle_claimed(time_str, worker_id, payload)
        elif event_type in ["OTP_RECEIVED", "OTP_INTERCEPTED"]:
            self.handle_otp(time_str, payload)
        elif event_type == "BOOKING_SUCCESS":
            self.handle_success(time_str, worker_id, payload)
        elif event_type in ["BOOKING_FAILED", "BOOKING_ALREADY_EXISTS"]:
            self.handle_failure(time_str, worker_id, payload, event_type)
        elif event_type in ["WAF_CHALLENGE", "PROXY_BANNED", "LOGIN_FAILED"]:
            self.handle_security_block(time_str, worker_id, payload, event_type)
        elif event_type in ["LEASE_EXPIRED", "LEASE_ABANDONED"]:
            self.handle_lease_expiry(time_str, worker_id, payload, event_type)
        else:
            print(f"[{time_str}] {Colors.DIM}[EVENT: {event_type}]{Colors.RESET} ({worker_id}) {json.dumps(payload)[:100]}")

    def handle_slot_found(self, t: str, worker: str, p: dict):
        self.total_slots_found += 1
        vac = p.get("visa_center", "138")
        date = p.get("date", "Unknown")
        slots = p.get("slots", [])
        slot_count = len(slots)
        print(f"[{t}] {Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [S2: SLOTS DISCOVERED] {Colors.RESET} "
              f"{Colors.GREEN}{Colors.BOLD}{slot_count} Slot(s) open at Center {vac} for date {date}!{Colors.RESET} "
              f"{Colors.DIM}(Discovered by {worker}){Colors.RESET}")

    def handle_no_slots(self, t: str, worker: str, p: dict):
        vac = p.get("visa_center", "138")
        print(f"[{t}] {Colors.DIM}[S1: MONITOR]{Colors.RESET} Worker '{worker}' checked Center {vac}: No open slots. (OK)")

    def handle_dispatched(self, t: str, p: dict):
        self.total_dispatched += 1
        task_id = str(p.get("task_id", "?"))
        app_id = p.get("applicant_id", "?")
        vac = p.get("visa_center", "?")
        date = p.get("target_date", "?")
        time_slot = p.get("target_time", "?")

        self.in_flight_tasks[task_id] = {
            "stage": 3,
            "start_time": time.time(),
            "applicant_id": app_id,
            "center": vac,
            "slot": f"{date} @ {time_slot}"
        }

        print(f"[{t}] {Colors.CYAN}{Colors.BOLD}[S3: QUEUE DISPATCH]{Colors.RESET} "
              f"Applicant #{app_id} dispatched from Waitlist -> {Colors.BOLD}BookingTask #{task_id}{Colors.RESET} "
              f"({date} @ {time_slot} | Center {vac})")

    def handle_claimed(self, t: str, worker: str, p: dict):
        task_id = str(p.get("task_id", "?"))
        acc = p.get("account", "Account")
        if task_id in self.in_flight_tasks:
            self.in_flight_tasks[task_id]["stage"] = 4
            self.in_flight_tasks[task_id]["worker"] = worker
        else:
            self.in_flight_tasks[task_id] = {"stage": 4, "start_time": time.time(), "worker": worker}

        print(f"[{t}] {Colors.BLUE}{Colors.BOLD}[S4: BOOKER CLAIM]{Colors.RESET} "
              f"BookingTask #{task_id} CLAIMED by {Colors.BOLD}{worker}{Colors.RESET} (Using Portal Account: {acc})")

    def handle_otp(self, t: str, p: dict):
        otp = p.get("extracted_otp") or p.get("otp_code") or "12345"
        print(f"[{t}] {Colors.MAGENTA}{Colors.BOLD}[S5: OTP INTERCEPTED]{Colors.RESET} "
              f"SMS Verification Code captured: {Colors.BOLD}{otp}{Colors.RESET} -> Injecting into booking form...")

    def handle_success(self, t: str, worker: str, p: dict):
        self.total_confirmed += 1
        task_id = str(p.get("task_id", "?"))
        ref = p.get("reference_number", "N/A")
        app_id = p.get("applicant_id", "?")
        vac = p.get("visa_center", "?")

        duration = "?"
        if task_id in self.in_flight_tasks:
            duration = f"{time.time() - self.in_flight_tasks[task_id]['start_time']:.1f}s"
            del self.in_flight_tasks[task_id]

        print(f"\n[{t}] {Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [S6: CONFIRMATION SUCCESS] {Colors.RESET} "
              f"{Colors.GREEN}{Colors.BOLD}Appointment SECURED for Applicant #{app_id}!{Colors.RESET}\n"
              f"       {Colors.BOLD}Reference Code:{Colors.RESET} {Colors.YELLOW}{ref}{Colors.RESET} | "
              f"{Colors.BOLD}Center:{Colors.RESET} {vac} | {Colors.BOLD}Execution Time:{Colors.RESET} {duration} | "
              f"{Colors.BOLD}Queue Status:{Colors.RESET} {Colors.GREEN}BOOKED{Colors.RESET}\n")

    def handle_failure(self, t: str, worker: str, p: dict, event_type: str):
        self.total_failed += 1
        task_id = str(p.get("task_id", "?"))
        reason = p.get("reason", "Unknown failure")

        if task_id in self.in_flight_tasks:
            del self.in_flight_tasks[task_id]

        if "ALREADY" in str(reason).upper() or event_type == "BOOKING_ALREADY_EXISTS":
            print(f"[{t}] {Colors.YELLOW}{Colors.BOLD}[EDGE CASE: ALREADY BOOKED]{Colors.RESET} "
                  f"Task #{task_id}: Active appointment already exists on portal. "
                  f"Queue state updated to {Colors.YELLOW}CANCELLED{Colors.RESET}.")
        else:
            print(f"[{t}] {Colors.RED}{Colors.BOLD}[BOOKING FAILED]{Colors.RESET} "
                  f"Task #{task_id} failed: {reason}. (Worker: {worker})")

    def handle_security_block(self, t: str, worker: str, p: dict, event_type: str):
        reason = p.get("reason", "")
        print(f"[{t}] {Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} [SECURITY BLOCK: {event_type}] {Colors.RESET} "
              f"Worker {worker} encountered: {reason}\n"
              f"       {Colors.YELLOW}-> Action Required: Check Cloudflare/WAF bypass or proxy status.{Colors.RESET}")

    def handle_lease_expiry(self, t: str, worker: str, p: dict, event_type: str):
        print(f"[{t}] {Colors.YELLOW}[LEASE {event_type}]{Colors.RESET} "
              f"Lease expired for worker {worker}. Task auto-recovered to PENDING.")

    def check_stalls(self):
        now = time.time()
        for task_id, task in list(self.in_flight_tasks.items()):
            elapsed = now - task["start_time"]
            stage = task["stage"]
            if stage == 3 and elapsed > 20:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[WATCHDOG STALL WARNING: STAGE 3]{Colors.RESET} "
                      f"Task #{task_id} has been DISPATCHED for {elapsed:.0f}s without being CLAIMED by any Booker worker.\n"
                      f"       -> Likely Root Cause: No Booker worker running (`can_book=True`) or all portal accounts in COOLDOWN.")
            elif stage == 4 and elapsed > 45:
                print(f"[{self.format_time()}] {Colors.YELLOW}{Colors.BOLD}[WATCHDOG STALL WARNING: STAGE 4-5]{Colors.RESET} "
                      f"Task #{task_id} in-flight with {task.get('worker')} for {elapsed:.0f}s without completing.\n"
                      f"       -> Likely Root Cause: Waiting for SMS OTP, solving heavy captcha, or worker hung.")


async def start_observer(saas_url: str, api_key: str):
    client = WatchdogClient(saas_url, api_key)
    tracker = PipelineTracker(client)
    
    # Normalize URLs
    base_url = saas_url.rstrip("/")
    ws_protocol = "wss" if base_url.startswith("https") else "ws"
    host = base_url.split("://")[1]
    ws_url = f"{ws_protocol}://{host}/ws/live-logs"

    tracker.print_banner(base_url, ws_url)
    tracker.print_system_snapshot()

    # Stall check background task
    async def stall_checker():
        while True:
            await asyncio.sleep(5)
            tracker.check_stalls()

    asyncio.create_task(stall_checker())

    retry_delay = 3
    while True:
        try:
            print(f"[{tracker.format_time()}] Connecting to SaaS live WebSocket stream...")
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[{tracker.format_time()}] {Colors.GREEN}{Colors.BOLD}CONNECTED! Live Watchdog is actively monitoring the pipeline.{Colors.RESET}\n")
                retry_delay = 3
                while True:
                    message_raw = await ws.recv()
                    try:
                        event = json.loads(message_raw)
                        tracker.process_event(event)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[{tracker.format_time()}] {Colors.YELLOW}WebSocket disconnected ({e}). Reconnecting in {retry_delay}s...{Colors.RESET}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 15)


def main():
    parser = argparse.ArgumentParser(description="Live Pipeline Observer & Watchdog for Booking Automation")
    parser.add_argument("--saas-url", default=os.getenv("SAAS_BASE_URL", "https://keagent.alamiaconnect.com"),
                        help="Base URL of the SaaS control plane (default: https://keagent.alamiaconnect.com)")
    parser.add_argument("--api-key", default=os.getenv("WATCHDOG_API_KEY", "51129693340"),
                        help="API key for watchdog status and recovery endpoints (default: 51129693340)")
    parser.add_argument("--trigger-poll", action="store_true",
                        help="Immediately trigger monitoring assignments to poll right away")
    parser.add_argument("--reset-queue", action="store_true",
                        help="Immediately self-heal and reset stuck queue entries to PENDING")
    args = parser.parse_args()

    client = WatchdogClient(args.saas_url, args.api_key)

    if args.trigger_poll:
        res = client.trigger_poll()
        print("Trigger Poll Result:", res)
        return

    if args.reset_queue:
        res = client.reset_queue()
        print("Reset Queue Result:", res)
        return

    try:
        asyncio.run(start_observer(args.saas_url, args.api_key))
    except KeyboardInterrupt:
        print("\nObserver stopped by user.")


if __name__ == "__main__":
    main()
