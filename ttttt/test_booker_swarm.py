import time
import os
import sys
import argparse
import threading
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Setup path
sys.path.insert(0, os.path.abspath("ttttt/operator-agent"))
sys.path.insert(0, os.path.abspath("ttttt/operator-agent/core"))

from core.browser_persona import BrowserPersonaManager
from core.gvc_adapter import GVCAdapter
from mock_captcha import MockCaptchaService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s")

PORTAL_URL = "http://127.0.0.1:5001"
os.environ["BOOKING_PORTAL_URL"] = PORTAL_URL
os.environ["USE_MOCK_CAPTCHA"] = "true"

def run_single_worker(worker_idx: int, applicant_data: dict, slot_data: dict):
    worker_id = f"booker-worker-{worker_idx:02d}"
    persona = BrowserPersonaManager.get_persona_for_worker(worker_id)
    logging.info(f"[{worker_id}] Spawning with Persona '{persona.persona_id}' (TLS: {persona.tls_target}, Platform: {persona.sec_ch_ua_platform})...")
    
    captcha_svc = MockCaptchaService()
    adapter = GVCAdapter(captcha_service=captcha_svc, headless=True, persona=persona)
    adapter.cookie_file = f"cookies_test_{worker_idx}.pkl"
    
    # 1. Login
    username = f"agent_branch_{worker_idx}@kamalexpress.com"
    login_ok = adapter.login(username, "Password123!")
    if not login_ok:
        logging.error(f"[{worker_id}] Login failed!")
        return {"worker_id": worker_id, "success": False, "reason": "Login failed"}
        
    # 2. Inject applicant & slot payload
    applicant_data["periodslotid"] = slot_data["periodslotid"]
    applicant_data["target_time"] = slot_data["starttime"]
    applicant_data["target_date"] = slot_data["date"]
    adapter.inject_applicant_data(applicant_data, "137")
    
    # 3. Pre-OTP Captcha
    if not adapter.pass_pre_otp_captcha():
        logging.error(f"[{worker_id}] Pre-OTP Captcha failed!")
        return {"worker_id": worker_id, "success": False, "reason": "Captcha failed"}
        
    # 4. Trigger OTP
    if not adapter.request_otp():
        logging.error(f"[{worker_id}] OTP request failed!")
        return {"worker_id": worker_id, "success": False, "reason": "OTP request failed"}
        
    # 5. Fetch generated OTP from portal
    phone = applicant_data["phone"]
    otp_res = requests.get(f"{PORTAL_URL}/api/v1/onetimepassword/lookup/{phone}").json()
    otp_code = otp_res.get("otp", "12345")
    
    # 6. Final Booking Submission
    book_ok = adapter.submit_otp_and_book(otp_code)
    adapter.close()
    
    return {
        "worker_id": worker_id,
        "persona_id": persona.persona_id,
        "platform": persona.sec_ch_ua_platform,
        "applicant": f"{applicant_data['firstname']} {applicant_data['surname']}",
        "passport": applicant_data["passport"],
        "slot_id": slot_data["periodslotid"],
        "success": book_ok
    }

def main():
    parser = argparse.ArgumentParser(description="Test Polymorphic Booker Swarm")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers to test (default: 5)")
    args = parser.parse_args()
    
    num_workers = max(1, min(args.workers, 25))
    
    print("=" * 70)
    print(f"[START] POLYMORPHIC BOOKER SWARM VALIDATION ({num_workers} CONCURRENT WORKERS)")
    print("=" * 70)
    
    # 1. Reset Mock Portal
    requests.post(f"{PORTAL_URL}/telemetry/reset")
    
    # 2. Fetch available slots from portal
    slots_res = requests.put(f"{PORTAL_URL}/api/v1/periodslot/slots", json={"vac": {"id": 137}, "datefrom": "12/08/2026"}).json()
    available_slots = slots_res.get("returnobject", {}).get("slots", [])
    print(f"\n[Portal Status] Discovered {len(available_slots)} available slot windows.")
    
    # 3. Prepare unique applicants
    first_names = ["SHAHID", "AHMED", "ALI", "FATIMA", "AYESHA", "OMAR", "ZARA", "HASSAN", "SARA", "BILAL",
                   "USMAN", "ZAINAB", "HAMZA", "MARYAM", "TARIQ", "NOOR", "FAHAD", "HINA", "ADNAN", "RABIA",
                   "KASHIF", "ASIM", "NOMAN", "SAMI", "REHAN"]
    surnames = ["RIAZ", "KHAN", "SYED", "TARIQ", "MALIK", "SHEIKH", "CHAUDHRY", "RANA", "IQBAL", "BAIG",
                "BUTT", "GILLANI", "ABBASI", "SIDDIQUI", "MEMON", "QURESHI", "DAR", "MIRZA", "HASHMI", "WARRAICH",
                "JAVED", "AKHTAR", "NAEEM", "RASHEED", "LATIF"]
    
    applicants = []
    for i in range(num_workers):
        applicants.append({
            "firstname": first_names[i],
            "surname": surnames[i],
            "email": f"client{i+1}@kamalexpress.com",
            "phone": f"31651859{i:02d}",
            "phone_prefix_id": "197",
            "passport": f"PK88290{i:02d}",
            "passport_exp": "20/12/2030",
            "dob": "15/05/1992",
            "gender_id": "2" if i % 2 == 0 else "1",
            "nationality_id": "197"
        })
        
    start_time = time.time()
    
    # 4. Launch Parallel Booker Workers
    print(f"\n[Swarm Launch] Spinning up {num_workers} on-demand polymorphic booking workers...")
    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(run_single_worker, i + 1, applicants[i], available_slots[i])
            for i in range(num_workers)
        ]
        for f in as_completed(futures):
            results.append(f.result())
            
    elapsed = time.time() - start_time
    
    # 5. Inspect Results
    print("\n" + "=" * 70)
    print("[RESULTS] SWARM EXECUTION METRICS")
    print("=" * 70)
    success_count = sum(1 for r in results if r["success"])
    print(f"Total Workers Dispatched : {num_workers}")
    print(f"Successful Bookings      : {success_count}/{num_workers} ({success_count/num_workers*100:.1f}%)")
    print(f"Total Execution Time     : {elapsed:.2f} seconds")
    
    # 6. Verify Telemetry & Diversity from Mock Portal
    t_res = requests.get(f"{PORTAL_URL}/telemetry/fingerprints").json()
    bookings_data = t_res.get("bookings", [])
    telemetry_data = t_res.get("telemetry", [])
    
    distinct_user_agents = set(t["user_agent"] for t in telemetry_data if t["user_agent"])
    distinct_platforms = set(t["sec_ch_ua_platform"] for t in telemetry_data if t["sec_ch_ua_platform"])
    distinct_slots_booked = set(b["periodslotid"] for b in bookings_data)
    
    print("\n" + "-" * 70)
    print("[TELEMETRY] WAF FINGERPRINT DIVERSITY ANALYSIS")
    print("-" * 70)
    print(f"Total Portal Requests Captured : {len(telemetry_data)}")
    print(f"Unique Browser User-Agents     : {len(distinct_user_agents)} distinct profiles")
    for ua in distinct_user_agents:
        print(f"  * {ua}")
    print(f"Unique OS Platforms Reported   : {distinct_platforms}")
    print(f"Unique Slots Booked (No Collisions): {len(distinct_slots_booked)} of {num_workers}")
    
    # Assertions
    assert success_count == num_workers, f"Expected {num_workers} successes, got {success_count}"
    assert len(distinct_slots_booked) == num_workers, "Collision detected in booked slots!"
    
    print(f"\n[SUCCESS] ALL CHECKS PASSED: {num_workers}/{num_workers} SUCCESSFUL ON-DEMAND BOOKINGS WITH FULL DIVERSITY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
