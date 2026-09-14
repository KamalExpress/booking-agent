import time
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Mock GVC World Portal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK-GVC] %(levelname)s - %(message)s")

otps = {}
bookings = []
telemetry_log = []

SLOT_MATRIX = [
    {"periodslotid": 2528250 + i, "id": 2528250 + i, "starttime": f"{9 + (i // 2):02d}:{(i % 2) * 30:02d}", "endtime": f"{9 + (i // 2):02d}:{(i % 2) * 30 + 20:02d}", "isavailable": True, "isselectable": True, "date": "12/08/2026"}
    for i in range(25)
]

def record_telemetry(request: Request, endpoint: str):
    record = {
        "timestamp": time.time(),
        "endpoint": endpoint,
        "method": request.method,
        "ip": request.client.host if request.client else "127.0.0.1",
        "user_agent": request.headers.get("user-agent", ""),
        "sec_ch_ua": request.headers.get("sec-ch-ua", ""),
        "sec_ch_ua_platform": request.headers.get("sec-ch-ua-platform", ""),
        "sec_fetch_site": request.headers.get("sec-fetch-site", ""),
        "sec_fetch_mode": request.headers.get("sec-fetch-mode", ""),
        "sec_fetch_dest": request.headers.get("sec-fetch-dest", "")
    }
    telemetry_log.append(record)
    return record

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    record_telemetry(request, "GET /")
    return "<html><head><title>GVC Greece Visa Services</title></head><body>GVC World Portal Landing</body></html>"

@app.get("/favicon.ico")
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    record_telemetry(request, "GET /login")
    return "<html><body>Login Form</body></html>"

@app.post("/api/v1/auth/login")
async def auth_login(request: Request):
    t_record = record_telemetry(request, "POST /api/v1/auth/login")
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = data.get("username", "agent@example.com")
    
    logging.info(f"Login attempt for '{username}' (UA: {t_record['user_agent'][:40]}...)")
    
    user_payload = {
        "id": 931995,
        "username": username,
        "email": username,
        "firstname": "AGENT",
        "lastname": "OFFICE",
        "roles": ["ROLE_USER", "ROLE_AGENT"],
        "country": {"id": 19, "name": "PAKISTAN"},
        "vac": {"id": 137, "name": "Islamabad Visa Application Center"}
    }
    return {
        "code": "SUCCESS",
        "token": f"jwt-mock-token-{int(time.time())}",
        "user": user_payload
    }

@app.put("/api/v1/periodslot/slots")
async def get_slots(request: Request):
    record_telemetry(request, "PUT /api/v1/periodslot/slots")
    try:
        data = await request.json()
    except Exception:
        data = {}
    vac_id = data.get("vac", {}).get("id", 137) if isinstance(data.get("vac"), dict) else data.get("vac", 137)
    target_date = data.get("datefrom", "12/08/2026")
    
    avail_slots = [s for s in SLOT_MATRIX if s["isavailable"]]
    logging.info(f"Queried slots for VAC {vac_id} on {target_date}: {len(avail_slots)} available.")
    return {
        "code": "SUCCESS",
        "returnobject": {
            "vacId": vac_id,
            "date": target_date,
            "slots": avail_slots
        }
    }

@app.post("/api/v1/onetimepassword/sendOtpBookAppointment/{phone}/{prefix_id}")
async def send_otp(request: Request, phone: str, prefix_id: str):
    record_telemetry(request, f"POST /api/v1/onetimepassword/sendOtpBookAppointment/{phone}/{prefix_id}")
    clean_phone = str(phone).lstrip('0')
    generated_otp = "12345"
    otps[clean_phone] = generated_otp
    logging.info(f"Generated OTP '{generated_otp}' for phone +{prefix_id}-{clean_phone}")
    return {"code": "SUCCESS", "message": "OTP sent successfully"}

@app.get("/api/v1/onetimepassword/lookup/{phone}")
async def lookup_otp(phone: str):
    clean_phone = str(phone).lstrip('0')
    if clean_phone in otps:
        return {"phone": clean_phone, "otp": otps[clean_phone]}
    return JSONResponse(status_code=404, content={"error": "No OTP found"})

@app.post("/api/v1/appointments")
async def book_appointment_rest(request: Request):
    t_record = record_telemetry(request, "POST /api/v1/appointments")
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    phone = str(data.get("phonenumber", "")).lstrip('0')
    submitted_otp = str(data.get("onetimepassword", ""))
    applicants = data.get("applicants", [])
    vac = data.get("vac", "137")
    target_date = data.get("datefrom", "12/08/2026")
    selected_time = data.get("selectedtime", "12:00")
    
    expected_otp = otps.get(phone, "12345")
    if submitted_otp != expected_otp and submitted_otp != "12345":
        logging.error(f"OTP Mismatch for {phone}: got '{submitted_otp}', expected '{expected_otp}'")
        return JSONResponse(status_code=400, content={"code": "ERROR", "message": "Invalid OTP code"})
        
    if not applicants:
        return JSONResponse(status_code=400, content={"code": "ERROR", "message": "No applicant details provided"})
        
    applicant = applicants[0]
    periodslotid = int(applicant.get("periodslotid", 0) or 0)
    
    for slot in SLOT_MATRIX:
        if slot["periodslotid"] == periodslotid:
            slot["isavailable"] = False
            break
            
    booking_record = {
        "booking_id": f"GVC-GR-{len(bookings) + 1001}",
        "vac": vac,
        "date": target_date,
        "time": selected_time,
        "periodslotid": periodslotid,
        "applicant_name": f"{applicant.get('firstname')} {applicant.get('surname')}",
        "passport": applicant.get("passportnumber"),
        "phone": phone,
        "email": data.get("email"),
        "user_agent": t_record["user_agent"],
        "sec_ch_ua_platform": t_record["sec_ch_ua_platform"],
        "timestamp": time.time()
    }
    bookings.append(booking_record)
    logging.info(f"CONFIRMED BOOKING #{len(bookings)}: {booking_record['applicant_name']} (Passport: {booking_record['passport']}, Slot: {periodslotid}) via {t_record['user_agent'][:30]}...")
    
    return {
        "code": "SUCCESS",
        "returnobject": {
            "bookingId": booking_record["booking_id"],
            "appointmentStatus": "CONFIRMED",
            "vac": vac,
            "date": target_date,
            "time": selected_time
        }
    }

@app.post("/appointments/add")
async def book_appointment_legacy(request: Request):
    record_telemetry(request, "POST /appointments/add")
    return {"code": "SUCCESS", "status": "CONFIRMED"}

@app.api_route("/appointments/result/null", methods=["GET", "POST"])
async def booking_result():
    return {"code": "SUCCESS"}

@app.get("/telemetry/fingerprints")
async def get_telemetry():
    return {
        "total_requests": len(telemetry_log),
        "total_bookings": len(bookings),
        "telemetry": telemetry_log,
        "bookings": bookings
    }

@app.post("/telemetry/reset")
async def reset_telemetry():
    global telemetry_log, bookings, otps
    telemetry_log = []
    bookings = []
    otps = {}
    for slot in SLOT_MATRIX:
        slot["isavailable"] = True
    return {"status": "reset_successful"}

if __name__ == "__main__":
    logging.info("Starting Mock GVC Portal on http://127.0.0.1:5001...")
    uvicorn.run(app, host="127.0.0.1", port=5001, log_level="warning")
