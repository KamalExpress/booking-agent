import time
import logging
import datetime
import os
import json
import uuid
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import uvicorn

app = FastAPI(title="GVC World Consular Portal & Simulator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [GVC-SIMULATOR] %(levelname)s - %(message)s")

# In-Memory State
otps: Dict[str, str] = {}
bookings: List[Dict[str, Any]] = []
telemetry_log: List[Dict[str, Any]] = []
simulation_flags = {
    "waf_challenge_active": False,
    "rate_limit_active": False,
    "require_captcha": True
}

# Initial Slots Matrix
SLOT_MATRIX: List[Dict[str, Any]] = []

def generate_default_slots(start_date: str = None, days: int = 7, slots_per_day: int = 6):
    global SLOT_MATRIX
    SLOT_MATRIX.clear()
    
    if not start_date:
        base_dt = datetime.date.today() + datetime.timedelta(days=2)
    else:
        try:
            base_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            try:
                base_dt = datetime.datetime.strptime(start_date, "%d/%m/%Y").date()
            except Exception:
                base_dt = datetime.date.today() + datetime.timedelta(days=2)
                
    slot_id_counter = 2528000
    for day_offset in range(days):
        current_date = base_dt + datetime.timedelta(days=day_offset)
        date_str_iso = current_date.strftime("%Y-%m-%d")
        date_str_gvc = current_date.strftime("%d/%m/%Y")
        
        for s in range(slots_per_day):
            hour = 9 + (s * 30) // 60
            minute = (s * 30) % 60
            start_time = f"{hour:02d}:{minute:02d}"
            end_time = f"{hour:02d}:{(minute + 20):02d}"
            slot_id_counter += 1
            
            SLOT_MATRIX.append({
                "periodslotid": slot_id_counter,
                "id": slot_id_counter,
                "starttime": start_time,
                "endtime": end_time,
                "isavailable": True,
                "isselectable": True,
                "date": date_str_gvc,
                "date_iso": date_str_iso,
                "vac_id": "138",
                "vac_name": "Lahore Visa Application Center",
                "app_type": "26"
            })
    logging.info(f"Generated {len(SLOT_MATRIX)} slots across {days} days starting {base_dt.strftime('%d/%m/%Y')}.")

# Seed default slots on startup
generate_default_slots(days=5, slots_per_day=6)

def record_telemetry(request: Request, endpoint: str):
    record = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.time(),
        "time_str": datetime.datetime.now().strftime("%H:%M:%S"),
        "endpoint": endpoint,
        "method": request.method,
        "ip": request.client.host if request.client else "127.0.0.1",
        "user_agent": request.headers.get("user-agent", "Unknown"),
        "sec_ch_ua": request.headers.get("sec-ch-ua", ""),
        "sec_ch_ua_platform": request.headers.get("sec-ch-ua-platform", ""),
        "sec_fetch_site": request.headers.get("sec-fetch-site", ""),
        "sec_fetch_mode": request.headers.get("sec-fetch-mode", ""),
        "sec_fetch_dest": request.headers.get("sec-fetch-dest", "")
    }
    telemetry_log.insert(0, record)
    if len(telemetry_log) > 200:
        telemetry_log.pop()
    return record

# ==============================================================================
# GVC HUMAN WEB UI (Exact GVC Visual Identity & Interactive Booking Flow)
# ==============================================================================

GVC_HTML_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__ - Global Visa Center World</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        :root {
            --gvc-blue: #0b3a75;
            --gvc-gold: #c29b38;
            --gvc-navy: #061e3d;
        }
        .bg-gvc-blue { background-color: var(--gvc-blue); }
        .bg-gvc-navy { background-color: var(--gvc-navy); }
        .text-gvc-gold { color: var(--gvc-gold); }
        .border-gvc-gold { border-color: var(--gvc-gold); }
        .btn-gvc {
            background-color: var(--gvc-blue);
            color: white;
            transition: all 0.2s ease;
        }
        .btn-gvc:hover {
            background-color: #082d5c;
            box-shadow: 0 4px 12px rgba(11, 58, 117, 0.3);
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col font-sans">
    <div class="bg-gvc-navy text-white text-xs py-2 px-6 border-b border-slate-700/60">
        <div class="max-w-6xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-4">
                <span class="flex items-center gap-1.5 font-medium tracking-wide">
                    <i data-lucide="shield-check" class="w-4 h-4 text-gvc-gold"></i>
                    HELLENIC REPUBLIC &bull; VISA APPLICATION SERVICES
                </span>
                <span class="hidden sm:inline-block text-slate-400">|</span>
                <span class="hidden sm:inline-block text-slate-300">Authorized Visa Processing Operator</span>
            </div>
            <div class="flex items-center gap-4 text-slate-300">
                <a href="/admin" class="hover:text-gvc-gold transition-colors font-medium flex items-center gap-1">
                    <i data-lucide="settings" class="w-3.5 h-3.5"></i> Simulator Deck
                </a>
                <span>&bull;</span>
                <span class="flex items-center gap-1"><i data-lucide="globe" class="w-3.5 h-3.5"></i> English (EN)</span>
            </div>
        </div>
    </div>

    <header class="bg-white shadow-sm border-b border-slate-200">
        <div class="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
            <a href="/" class="flex items-center gap-3">
                <div class="w-10 h-10 rounded bg-gvc-blue flex items-center justify-center text-white font-bold text-xl shadow-md border-b-2 border-gvc-gold">
                    G
                </div>
                <div>
                    <h1 class="text-xl font-bold text-slate-900 tracking-tight leading-none">GVC WORLD</h1>
                    <p class="text-[11px] text-slate-500 font-medium tracking-wider uppercase mt-0.5">Global Visa Center &bull; Greece Services</p>
                </div>
            </a>
            <div class="flex items-center gap-3">
                <a href="/" class="text-sm font-semibold text-gvc-blue hover:text-blue-900 px-3 py-1.5 rounded transition-colors">Book Appointment</a>
                <a href="/admin" class="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded border border-slate-300 hover:border-slate-400 transition-colors">Simulator Admin</a>
            </div>
        </div>
    </header>

    <main class="flex-grow max-w-6xl w-full mx-auto p-6">
        __CONTENT__
    </main>

    <footer class="bg-gvc-navy text-slate-400 text-xs py-8 px-6 mt-12 border-t border-slate-800">
        <div class="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
            <p>&copy; 2026 GVCW Global Visa Center World. All rights reserved.</p>
            <div class="flex gap-6">
                <a href="/admin" class="hover:text-white transition-colors">Simulator Telemetry</a>
                <a href="#" class="hover:text-white transition-colors">Security & WAF Shield</a>
                <a href="#" class="hover:text-white transition-colors">Privacy Policy</a>
            </div>
        </div>
    </footer>

    <script>
        lucide.createIcons();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def human_portal_home(request: Request):
    record_telemetry(request, "GET /")
    
    avail_count = sum(1 for s in SLOT_MATRIX if s["isavailable"])
    dates_available = sorted(list(set(s["date"] for s in SLOT_MATRIX if s["isavailable"])))
    next_date_label = dates_available[0] if dates_available else "No Open Dates"
    
    content = """
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-8 mb-8">
        <div class="max-w-3xl">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-gvc-blue border border-blue-200 mb-3">
                <i data-lucide="calendar" class="w-3.5 h-3.5"></i> Live Slot Matrix Online
            </span>
            <h2 class="text-3xl font-extrabold text-slate-900 tracking-tight">Schedule Your Visa Appointment</h2>
            <p class="text-slate-600 mt-2 text-sm leading-relaxed">
                Welcome to the official appointment scheduling portal for the Embassy of Greece in Pakistan. Select your preferred application center, date, and complete your verification to secure your submission slot.
            </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8 pt-8 border-t border-slate-100">
            <div class="flex items-center gap-3 p-4 rounded-lg bg-slate-50 border border-slate-200">
                <div class="p-2.5 rounded-lg bg-blue-100 text-gvc-blue">
                    <i data-lucide="map-pin" class="w-5 h-5"></i>
                </div>
                <div>
                    <p class="text-xs font-medium text-slate-500 uppercase">Visa Centers</p>
                    <p class="text-sm font-bold text-slate-900">Lahore (138) &bull; Islamabad (137)</p>
                </div>
            </div>
            
            <div class="flex items-center gap-3 p-4 rounded-lg bg-slate-50 border border-slate-200">
                <div class="p-2.5 rounded-lg bg-emerald-100 text-emerald-700">
                    <i data-lucide="check-circle" class="w-5 h-5"></i>
                </div>
                <div>
                    <p class="text-xs font-medium text-slate-500 uppercase">Available Slots</p>
                    <p class="text-sm font-bold text-emerald-700">__AVAIL_COUNT__ Open Appointments</p>
                </div>
            </div>

            <div class="flex items-center gap-3 p-4 rounded-lg bg-slate-50 border border-slate-200">
                <div class="p-2.5 rounded-lg bg-amber-100 text-amber-700">
                    <i data-lucide="clock" class="w-5 h-5"></i>
                </div>
                <div>
                    <p class="text-xs font-medium text-slate-500 uppercase">Next Slot Date</p>
                    <p class="text-sm font-bold text-slate-900">__NEXT_DATE__</p>
                </div>
            </div>
        </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="bg-slate-50 border-b border-slate-200 px-8 py-4 flex items-center justify-between">
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
                <span class="w-6 h-6 rounded-full bg-gvc-blue text-white text-xs flex items-center justify-center font-bold">1</span>
                Step 1: Select Application Center & Appointment Type
            </h3>
            <span class="text-xs text-slate-500">FastAPI High-Speed Core</span>
        </div>

        <form id="bookingFlowForm" class="p-8 space-y-6" onsubmit="event.preventDefault(); proceedToStep2();">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Visa Application Center <span class="text-red-500">*</span></label>
                    <select id="vacSelect" class="w-full bg-slate-50 border border-slate-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none font-medium">
                        <option value="138" selected>Lahore Visa Application Center (VAC 138)</option>
                        <option value="137">Islamabad Visa Application Center (VAC 137)</option>
                    </select>
                </div>

                <div>
                    <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Appointment Category <span class="text-red-500">*</span></label>
                    <select id="typeSelect" class="w-full bg-slate-50 border border-slate-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none font-medium">
                        <option value="26" selected>Long-Term Type D (Seasonal / Dependent Employment) - Code 26</option>
                        <option value="0">Submission Schengen Visa (Short Term - Type C) - Code 0</option>
                        <option value="2">National Visa (Long Term - Type D) - Code 2</option>
                        <option value="5">Premium Lounge Service - Code 5</option>
                    </select>
                </div>
            </div>

            <div class="pt-4 flex justify-end">
                <button type="submit" class="btn-gvc px-6 py-3 rounded-lg font-bold text-sm flex items-center gap-2">
                    Continue to Slot Selection <i data-lucide="arrow-right" class="w-4 h-4"></i>
                </button>
            </div>
        </form>
    </div>

    <div id="step2Section" class="hidden mt-8 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="bg-slate-50 border-b border-slate-200 px-8 py-4 flex items-center justify-between">
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
                <span class="w-6 h-6 rounded-full bg-gvc-blue text-white text-xs flex items-center justify-center font-bold">2</span>
                Step 2: Available Appointment Timeslots
            </h3>
            <button onclick="document.getElementById('step2Section').classList.add('hidden')" class="text-slate-400 hover:text-slate-600">
                <i data-lucide="x" class="w-5 h-5"></i>
            </button>
        </div>

        <div class="p-8">
            <p class="text-xs text-slate-500 mb-4">Click an available slot to proceed with applicant registration:</p>
            <div id="slotsGrid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3"></div>
        </div>
    </div>

    <div id="applicantModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in duration-150 text-left">
            <div class="bg-gvc-navy p-6 text-white flex justify-between items-center border-b border-slate-700">
                <div>
                    <h3 class="text-lg font-bold">Applicant Information</h3>
                    <p class="text-xs text-slate-300">Selected Slot: <span id="modalSlotSummary" class="font-bold text-gvc-gold">-</span></p>
                </div>
                <button onclick="document.getElementById('applicantModal').classList.add('hidden')" class="text-slate-400 hover:text-white">
                    <i data-lucide="x" class="w-5 h-5"></i>
                </button>
            </div>

            <form id="applicantDetailsForm" class="p-6 space-y-4 text-sm" onsubmit="event.preventDefault(); submitApplicantAndTriggerOtp();">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">First Name *</label>
                        <input type="text" id="appFirstName" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm" value="AMR">
                    </div>
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">Surname *</label>
                        <input type="text" id="appLastName" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm" value="SHAH">
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">Passport Number *</label>
                        <input type="text" id="appPassport" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm font-mono uppercase" value="PK9482019">
                    </div>
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">Date of Birth *</label>
                        <input type="text" id="appDob" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm" value="15/08/1992">
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">Phone Number (SIM) *</label>
                        <input type="text" id="appPhone" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm" value="3345112969">
                    </div>
                    <div>
                        <label class="block text-[11px] font-bold text-slate-600 uppercase mb-1">Email Address *</label>
                        <input type="email" id="appEmail" required class="w-full bg-slate-50 border border-slate-300 rounded p-2.5 text-sm" value="amr.shah@gmail.com">
                    </div>
                </div>

                <div id="otpSection" class="hidden mt-6 p-4 rounded-xl bg-blue-50 border border-blue-200">
                    <div class="flex justify-between items-center mb-2">
                        <label class="text-xs font-bold text-gvc-blue uppercase tracking-wider">SMS OTP Verification Code</label>
                        <span id="simulatedOtpBadge" class="text-xs px-2 py-0.5 rounded bg-blue-200 text-blue-900 font-mono font-bold">Simulated OTP: 12345</span>
                    </div>
                    <p class="text-xs text-slate-600 mb-3">A 5-digit verification code has been dispatched to your mobile phone number.</p>
                    <input type="text" id="enteredOtp" placeholder="Enter 5-digit OTP" class="w-full bg-white border border-blue-300 rounded p-3 text-center text-lg tracking-widest font-mono font-bold text-slate-900">
                </div>

                <div class="pt-4 flex justify-end gap-3 border-t border-slate-200 mt-4">
                    <button type="button" onclick="document.getElementById('applicantModal').classList.add('hidden')" class="px-4 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg">Cancel</button>
                    <button type="submit" id="submitBtn" class="btn-gvc px-5 py-2.5 text-xs font-bold rounded-lg flex items-center gap-2">
                        Request SMS OTP &bull; Step 4
                    </button>
                </div>
            </form>
        </div>
    </div>

    <div id="confirmationSlipModal" class="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4 overflow-y-auto">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden text-left my-8">
            <div id="printableSlipCard" class="p-8 bg-white text-slate-900">
                <div class="flex justify-between items-start border-b-2 border-gvc-blue pb-6 mb-6">
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 rounded bg-gvc-blue flex items-center justify-center text-white font-bold text-2xl border-b-2 border-gvc-gold">G</div>
                        <div>
                            <h2 class="text-xl font-bold text-gvc-blue">GVC WORLD &bull; EMBASSY OF GREECE</h2>
                            <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Official Visa Appointment Confirmation Slip</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="inline-block px-3 py-1 rounded bg-emerald-100 text-emerald-800 border border-emerald-300 text-xs font-bold uppercase tracking-wider">CONFIRMED</span>
                        <p id="slipBookingId" class="text-sm font-mono font-bold text-slate-900 mt-1">GVC-ISB-2026-9482</p>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-6 p-6 rounded-xl bg-slate-50 border border-slate-200 text-sm mb-6">
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Applicant Name</p>
                        <p id="slipApplicantName" class="text-base font-bold text-slate-900 mt-0.5">AMR SHAH</p>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Passport Number</p>
                        <p id="slipPassport" class="text-base font-mono font-bold text-gvc-blue mt-0.5">PK9482019</p>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Appointment Date & Time</p>
                        <p id="slipDateTime" class="text-sm font-bold text-slate-900 mt-0.5">12/08/2026 at 09:30 AM</p>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Application Center</p>
                        <p id="slipCenter" class="text-sm font-medium text-slate-900 mt-0.5">Lahore Visa Application Center (VAC 138)</p>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Category / Visa Type</p>
                        <p class="text-sm font-medium text-slate-900 mt-0.5">Type D National (Long Stay #26)</p>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Verification Status</p>
                        <p class="text-xs font-semibold text-emerald-700 mt-1 flex items-center gap-1">
                            <i data-lucide="shield-check" class="w-4 h-4"></i> OTP Verified & Secured
                        </p>
                    </div>
                </div>

                <div class="p-4 bg-slate-100 rounded-lg text-center border border-slate-300">
                    <p class="font-mono text-2xl tracking-widest text-slate-800 font-bold">* GVC-2026-9482019 *</p>
                    <p class="text-[10px] text-slate-500 uppercase mt-1">Scan at Center Reception for Priority Queue Entry</p>
                </div>
            </div>

            <div class="p-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3">
                <button onclick="document.getElementById('confirmationSlipModal').classList.add('hidden')" class="px-4 py-2 text-xs font-semibold text-slate-600 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg">Close</button>
                <button onclick="downloadSlipAsImage()" class="btn-gvc px-4 py-2 text-xs font-bold rounded-lg flex items-center gap-1.5">
                    <i data-lucide="download" class="w-3.5 h-3.5"></i> Download Screenshot (PNG)
                </button>
                <button onclick="window.print()" class="px-4 py-2 text-xs font-bold bg-slate-800 hover:bg-slate-900 text-white rounded-lg flex items-center gap-1.5">
                    <i data-lucide="printer" class="w-3.5 h-3.5"></i> Print PDF Slip
                </button>
            </div>
        </div>
    </div>

    <script>
        let selectedSlot = null;
        let isOtpRequested = false;

        async function proceedToStep2() {
            const vac = document.getElementById('vacSelect').value;
            const res = await fetch('/api/v1/periodslot/slots', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vac: vac, datefrom: '12/08/2026' })
            });
            const data = await res.json();
            const slots = (data.returnobject && data.returnobject.slots) ? data.returnobject.slots : [];
            
            const grid = document.getElementById('slotsGrid');
            grid.innerHTML = '';
            
            if (slots.length === 0) {
                grid.innerHTML = '<p class="text-xs text-red-500 col-span-3">No available slots found for this center. Try triggering a slot drop from the Simulator Deck (/admin).</p>';
            } else {
                slots.forEach(s => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'p-3 rounded-lg border border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-400 text-left transition-all';
                    btn.innerHTML = `
                        <p class="text-xs font-bold text-slate-900">${s.date}</p>
                        <p class="text-sm font-extrabold text-gvc-blue mt-0.5">${s.starttime} - ${s.endtime}</p>
                        <span class="inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">Available</span>
                    `;
                    btn.onclick = () => openApplicantModal(s);
                    grid.appendChild(btn);
                });
            }
            
            document.getElementById('step2Section').classList.remove('hidden');
            document.getElementById('step2Section').scrollIntoView({ behavior: 'smooth' });
            lucide.createIcons();
        }

        function openApplicantModal(slot) {
            selectedSlot = slot;
            document.getElementById('modalSlotSummary').innerText = `${slot.date} at ${slot.starttime} (Slot #${slot.periodslotid})`;
            document.getElementById('applicantModal').classList.remove('hidden');
            document.getElementById('otpSection').classList.add('hidden');
            document.getElementById('submitBtn').innerText = 'Request SMS OTP • Step 4';
            isOtpRequested = false;
            lucide.createIcons();
        }

        async function submitApplicantAndTriggerOtp() {
            const phone = document.getElementById('appPhone').value;
            
            if (!isOtpRequested) {
                const res = await fetch(`/api/v1/onetimepassword/sendOtpBookAppointment/${phone}/197`, {
                    method: 'POST'
                });
                const data = await res.json();
                
                document.getElementById('otpSection').classList.remove('hidden');
                document.getElementById('enteredOtp').value = '12345';
                document.getElementById('submitBtn').innerText = 'Confirm & Finalize Booking • Step 5';
                isOtpRequested = true;
            } else {
                const otp = document.getElementById('enteredOtp').value;
                const payload = {
                    onetimepassword: otp,
                    phonenumber: phone,
                    email: document.getElementById('appEmail').value,
                    vac: document.getElementById('vacSelect').value,
                    datefrom: selectedSlot.date,
                    selectedtime: selectedSlot.starttime,
                    applicants: [{
                        firstname: document.getElementById('appFirstName').value,
                        surname: document.getElementById('appLastName').value,
                        passportnumber: document.getElementById('appPassport').value,
                        periodslotid: selectedSlot.periodslotid
                    }]
                };

                const res = await fetch('/api/v1/appointments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.code === 'SUCCESS') {
                    document.getElementById('applicantModal').classList.add('hidden');
                    
                    document.getElementById('slipApplicantName').innerText = document.getElementById('appFirstName').value + ' ' + document.getElementById('appLastName').value;
                    document.getElementById('slipPassport').innerText = document.getElementById('appPassport').value;
                    document.getElementById('slipDateTime').innerText = `${selectedSlot.date} at ${selectedSlot.starttime}`;
                    document.getElementById('slipBookingId').innerText = data.returnobject ? data.returnobject.bookingId : 'GVC-2026-CONF';
                    
                    document.getElementById('confirmationSlipModal').classList.remove('hidden');
                    proceedToStep2();
                } else {
                    alert('Booking Failed: ' + (data.message || 'Error occurred'));
                }
            }
            lucide.createIcons();
        }

        function downloadSlipAsImage() {
            const card = document.getElementById('printableSlipCard');
            html2canvas(card, { scale: 2 }).then(canvas => {
                const link = document.createElement('a');
                link.download = `GVC_Booking_Confirmation_${document.getElementById('slipPassport').innerText}.png`;
                link.href = canvas.toDataURL('image/png');
                link.click();
            });
        }
    </script>
    """
    
    content = content.replace("__AVAIL_COUNT__", str(avail_count)).replace("__NEXT_DATE__", next_date_label)
    html = GVC_HTML_BASE.replace("__TITLE__", "Visa Appointment Scheduling").replace("__CONTENT__", content)
    return html

# ==============================================================================
# SIMULATOR ADMIN CONSOLE (/admin: Custom Date Range, Telemetry, WAF Toggles)
# ==============================================================================

@app.get("/admin", response_class=HTMLResponse)
async def simulator_admin_deck(request: Request):
    record_telemetry(request, "GET /admin")
    
    avail_count = sum(1 for s in SLOT_MATRIX if s["isavailable"])
    total_count = len(SLOT_MATRIX)
    
    telemetry_rows = ""
    for t in telemetry_log[:15]:
        telemetry_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50 text-xs">
            <td class="p-3 font-mono text-slate-500">{t['time_str']}</td>
            <td class="p-3 font-bold text-gvc-blue">{t['method']} {t['endpoint']}</td>
            <td class="p-3 font-mono text-slate-600">{t['ip']}</td>
            <td class="p-3 text-slate-700 truncate max-w-xs">{t['user_agent'][:40]}...</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-800">{t['sec_ch_ua_platform'] or 'Standard'}</span></td>
        </tr>
        """
        
    booking_rows = ""
    for b in reversed(bookings[-10:]):
        booking_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50 text-xs">
            <td class="p-3 font-mono font-bold text-emerald-700">{b['booking_id']}</td>
            <td class="p-3 font-bold text-slate-900">{b['applicant_name']}</td>
            <td class="p-3 font-mono text-slate-600">{b['passport']}</td>
            <td class="p-3">{b['date']} @ {b['time']}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">CONFIRMED</span></td>
        </tr>
        """
    if not booking_rows:
        booking_rows = '<tr><td colspan="5" class="p-6 text-center text-xs text-slate-400">No bookings recorded yet.</td></tr>'

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    next_week_str = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    waf_state_class = "bg-red-400" if simulation_flags["waf_challenge_active"] else "bg-emerald-400"
    waf_state_label = "CHALLENGE ACTIVE" if simulation_flags["waf_challenge_active"] else "PASSIVE"
    waf_btn_class = "bg-red-600 text-white" if simulation_flags["waf_challenge_active"] else "bg-slate-200 text-slate-700"
    waf_btn_label = "ACTIVE" if simulation_flags["waf_challenge_active"] else "OFF"
    rate_btn_class = "bg-red-600 text-white" if simulation_flags["rate_limit_active"] else "bg-slate-200 text-slate-700"
    rate_btn_label = "ACTIVE" if simulation_flags["rate_limit_active"] else "OFF"

    content = f"""
    <div class="bg-gvc-navy text-white rounded-xl p-8 mb-8 shadow-md">
        <div class="flex justify-between items-center">
            <div>
                <span class="px-2.5 py-1 rounded text-xs font-bold bg-gvc-gold text-slate-950 uppercase tracking-wider">Simulator Command Center</span>
                <h2 class="text-3xl font-extrabold tracking-tight mt-2">GVC World &bull; Consular Core Simulator</h2>
                <p class="text-slate-300 text-sm mt-1">Control slot releases, simulate WAF challenges, and inspect live worker telemetry.</p>
            </div>
            <div class="flex gap-3">
                <a href="/" class="btn-gvc px-4 py-2.5 rounded-lg text-xs font-bold flex items-center gap-1.5 border border-white/20">
                    <i data-lucide="external-link" class="w-4 h-4"></i> View Human Web UI
                </a>
            </div>
        </div>

        <div class="grid grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-700/60 text-xs">
            <div>
                <p class="text-slate-400 uppercase font-semibold text-[10px]">Open Slots</p>
                <p class="text-2xl font-extrabold text-emerald-400 mt-0.5">{avail_count} / {total_count}</p>
            </div>
            <div>
                <p class="text-slate-400 uppercase font-semibold text-[10px]">Confirmed Bookings</p>
                <p class="text-2xl font-extrabold text-gvc-gold mt-0.5">{len(bookings)}</p>
            </div>
            <div>
                <p class="text-slate-400 uppercase font-semibold text-[10px]">HTTP Telemetry Hits</p>
                <p class="text-2xl font-extrabold text-blue-400 mt-0.5">{len(telemetry_log)}</p>
            </div>
            <div>
                <p class="text-slate-400 uppercase font-semibold text-[10px]">WAF Simulator</p>
                <p class="text-sm font-bold text-slate-200 mt-1 flex items-center gap-1">
                    <span class="w-2.5 h-2.5 rounded-full {waf_state_class}"></span>
                    {waf_state_label}
                </p>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        <div class="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2 mb-4">
                <i data-lucide="calendar-plus" class="w-5 h-5 text-gvc-blue"></i>
                Custom Date & Date Range Slot Release Controller
            </h3>
            
            <form action="/admin/slots/release" method="POST" class="space-y-4 text-xs">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block font-bold text-slate-700 mb-1">Start Date (From) *</label>
                        <input type="date" name="start_date" value="{today_str}" required class="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs font-semibold">
                    </div>
                    <div>
                        <label class="block font-bold text-slate-700 mb-1">End Date (To) *</label>
                        <input type="date" name="end_date" value="{next_week_str}" required class="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs font-semibold">
                    </div>
                </div>

                <div class="grid grid-cols-3 gap-4">
                    <div>
                        <label class="block font-bold text-slate-700 mb-1">Visa Center</label>
                        <select name="vac_id" class="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs">
                            <option value="138" selected>Lahore (138)</option>
                            <option value="137">Islamabad (137)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block font-bold text-slate-700 mb-1">Slots Per Day</label>
                        <input type="number" name="slots_per_day" value="8" min="1" max="50" class="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs">
                    </div>
                    <div>
                        <label class="block font-bold text-slate-700 mb-1">Interval (Mins)</label>
                        <select name="interval_mins" class="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs">
                            <option value="30" selected>30 Minutes</option>
                            <option value="15">15 Minutes</option>
                            <option value="60">60 Minutes</option>
                        </select>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-4 border-t border-slate-100">
                    <span class="text-[11px] text-slate-500">Generates instant matrix for automated scrapers & human users</span>
                    <div class="flex gap-2">
                        <a href="/admin/slots/clear" class="px-3 py-2 rounded-lg bg-red-50 text-red-700 hover:bg-red-100 font-bold text-xs border border-red-200">
                            Clear All Slots
                        </a>
                        <button type="submit" class="btn-gvc px-5 py-2 rounded-lg font-bold text-xs flex items-center gap-1.5 shadow-sm">
                            <i data-lucide="zap" class="w-3.5 h-3.5"></i> Release Slots Across Range
                        </button>
                    </div>
                </div>
            </form>
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
            <div>
                <h3 class="text-base font-bold text-slate-900 flex items-center gap-2 mb-4">
                    <i data-lucide="shield-alert" class="w-5 h-5 text-amber-600"></i>
                    WAF & Rate-Limit Simulator
                </h3>
                <p class="text-xs text-slate-600 mb-4">Inject simulated Cloudflare challenges and 429 rate limits to verify worker error recovery.</p>
                
                <div class="space-y-3 text-xs">
                    <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200">
                        <div>
                            <p class="font-bold text-slate-800">Cloudflare 403 Challenge</p>
                            <p class="text-[10px] text-slate-500">Forces captcha challenge on API calls</p>
                        </div>
                        <a href="/admin/toggle-waf" class="px-3 py-1 rounded font-bold text-xs {waf_btn_class}">
                            {waf_btn_label}
                        </a>
                    </div>

                    <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200">
                        <div>
                            <p class="font-bold text-slate-800">HTTP 429 Rate Limiter</p>
                            <p class="text-[10px] text-slate-500">Blocks bursts > 10 req/sec</p>
                        </div>
                        <a href="/admin/toggle-rate-limit" class="px-3 py-1 rounded font-bold text-xs {rate_btn_class}">
                            {rate_btn_label}
                        </a>
                    </div>
                </div>
            </div>

            <div class="pt-4 border-t border-slate-100 flex justify-between items-center text-xs">
                <a href="/telemetry/reset" class="text-slate-500 hover:text-slate-800 font-medium">Reset Telemetry Logs</a>
                <span class="text-slate-400 text-[10px]">Port 5001 Standalone</span>
            </div>
        </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-8">
        <div class="bg-slate-50 border-b border-slate-200 px-6 py-4 flex justify-between items-center">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
                <i data-lucide="book-check" class="w-4 h-4 text-emerald-600"></i>
                Live Confirmed Bookings Ledger
            </h3>
            <span class="text-xs text-slate-500 font-mono">Total: {len(bookings)}</span>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-50/50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        <th class="p-3">Booking ID</th>
                        <th class="p-3">Applicant Name</th>
                        <th class="p-3">Passport</th>
                        <th class="p-3">Appointment Schedule</th>
                        <th class="p-3">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {booking_rows}
                </tbody>
            </table>
        </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="bg-slate-50 border-b border-slate-200 px-6 py-4 flex justify-between items-center">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
                <i data-lucide="activity" class="w-4 h-4 text-gvc-blue"></i>
                Real-Time Worker Telemetry & TLS Fingerprint Radar
            </h3>
            <span class="text-xs text-slate-500">Live HTTP Stream</span>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-50/50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        <th class="p-3">Time</th>
                        <th class="p-3">REST Route</th>
                        <th class="p-3">Source IP</th>
                        <th class="p-3">User-Agent / Persona</th>
                        <th class="p-3">Platform</th>
                    </tr>
                </thead>
                <tbody>
                    {telemetry_rows}
                </tbody>
            </table>
        </div>
    </div>
    """

    html = GVC_HTML_BASE.replace("__TITLE__", "Simulator Command Deck").replace("__CONTENT__", content)
    return html

@app.post("/admin/slots/release")
async def admin_release_slots(
    start_date: str = Form(...),
    end_date: str = Form(...),
    vac_id: str = Form("138"),
    slots_per_day: int = Form(8),
    interval_mins: int = Form(30)
):
    try:
        dt_from = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        dt_to = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        days_count = max(1, (dt_to - dt_from).days + 1)
    except Exception:
        dt_from = datetime.date.today()
        days_count = 7
        
    generate_default_slots(start_date=dt_from.strftime("%Y-%m-%d"), days=days_count, slots_per_day=slots_per_day)
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/slots/clear")
async def admin_clear_slots():
    global SLOT_MATRIX
    SLOT_MATRIX.clear()
    logging.info("Flushed all available slots from matrix.")
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/toggle-waf")
async def admin_toggle_waf():
    simulation_flags["waf_challenge_active"] = not simulation_flags["waf_challenge_active"]
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/toggle-rate-limit")
async def admin_toggle_rate_limit():
    simulation_flags["rate_limit_active"] = not simulation_flags["rate_limit_active"]
    return RedirectResponse(url="/admin", status_code=303)

# ==============================================================================
# GVC REST API ENGINE (Exact GVC Contracts for Automated Scrapers & Bookers)
# ==============================================================================

@app.post("/api/v1/auth/login")
async def api_auth_login(request: Request):
    t_record = record_telemetry(request, "POST /api/v1/auth/login")
    if simulation_flags["waf_challenge_active"]:
        return JSONResponse(status_code=403, content={"code": "FORBIDDEN", "message": "Cloudflare Challenge Required"})
        
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    username = data.get("username", "agent@kamalexpress.com")
    logging.info(f"API Login authenticated for '{username}' (UA: {t_record['user_agent'][:30]}...)")
    
    return {
        "code": "SUCCESS",
        "token": f"jwt-mock-token-{int(time.time())}",
        "user": {
            "id": 931995,
            "username": username,
            "email": username,
            "firstname": "AGENT",
            "lastname": "OFFICE",
            "roles": ["ROLE_USER", "ROLE_AGENT"],
            "country": {"id": 19, "name": "PAKISTAN"},
            "vac": {"id": 138, "name": "Lahore Visa Application Center"}
        }
    }

@app.put("/api/v1/periodslot/slots")
async def api_query_slots(request: Request):
    record_telemetry(request, "PUT /api/v1/periodslot/slots")
    if simulation_flags["waf_challenge_active"]:
        return JSONResponse(status_code=403, content={"code": "FORBIDDEN", "message": "Cloudflare Challenge Required"})
        
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    vac_id = str(data.get("vac", {}).get("id", "138") if isinstance(data.get("vac"), dict) else data.get("vac", "138"))
    target_date = data.get("datefrom", "")
    
    avail_slots = [s for s in SLOT_MATRIX if s["isavailable"]]
    
    logging.info(f"API Query slots for VAC {vac_id}: returning {len(avail_slots)} available slots.")
    return {
        "code": "SUCCESS",
        "returnobject": {
            "vacId": vac_id,
            "date": target_date or (avail_slots[0]["date"] if avail_slots else "12/08/2026"),
            "slots": avail_slots
        }
    }

@app.post("/sendOtpBookAppointment")
@app.post("/api/v1/onetimepassword/sendOtpBookAppointment/{phone}/{prefix_id}")
async def api_send_otp(request: Request, phone: str = "", prefix_id: str = "197"):
    record_telemetry(request, f"POST /sendOtpBookAppointment phone={phone}")
    clean_phone = str(phone).lstrip('0')
    otps[clean_phone] = "12345"
    logging.info(f"SMS OTP dispatched for SIM +92-{clean_phone}: [Code: 12345]")
    return {
        "code": "SUCCESS",
        "status": "OTP_SENT",
        "message": f"Verification code sent to {clean_phone}"
    }

@app.get("/api/v1/onetimepassword/lookup/{phone}")
async def api_lookup_otp(phone: str):
    clean_phone = str(phone).lstrip('0')
    otp_val = otps.get(clean_phone, "12345")
    return {"code": "SUCCESS", "phone": clean_phone, "otp": otp_val}

@app.post("/api/v1/appointments")
@app.post("/appointments/add")
async def api_book_appointment(request: Request):
    t_record = record_telemetry(request, "POST /api/v1/appointments")
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    phone = str(data.get("phonenumber", "")).lstrip('0')
    submitted_otp = str(data.get("onetimepassword", ""))
    applicants = data.get("applicants", [])
    vac = str(data.get("vac", "138"))
    target_date = data.get("datefrom", "12/08/2026")
    selected_time = data.get("selectedtime", "09:30")
    
    expected_otp = otps.get(phone, "12345")
    if submitted_otp != expected_otp and submitted_otp != "12345":
        logging.error(f"OTP Mismatch for {phone}: got '{submitted_otp}', expected '{expected_otp}'")
        return JSONResponse(status_code=400, content={"code": "ERROR", "message": "Invalid OTP verification code"})
        
    if not applicants:
        return JSONResponse(status_code=400, content={"code": "ERROR", "message": "No applicant data in booking payload"})
        
    app_item = applicants[0]
    periodslotid = int(app_item.get("periodslotid", 0) or 0)
    
    for slot in SLOT_MATRIX:
        if slot["periodslotid"] == periodslotid:
            slot["isavailable"] = False
            break
            
    booking_id = f"GVC-GR-{len(bookings) + 9482}"
    booking_record = {
        "booking_id": booking_id,
        "vac": vac,
        "date": target_date,
        "time": selected_time,
        "periodslotid": periodslotid,
        "applicant_name": f"{app_item.get('firstname')} {app_item.get('surname')}",
        "passport": app_item.get("passportnumber"),
        "phone": phone,
        "email": data.get("email"),
        "user_agent": t_record["user_agent"],
        "sec_ch_ua_platform": t_record["sec_ch_ua_platform"],
        "timestamp": time.time(),
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    bookings.append(booking_record)
    logging.info(f"CONFIRMED APPOINTMENT #{len(bookings)}: {booking_record['applicant_name']} (Ref: {booking_id}) via {t_record['user_agent'][:30]}...")
    
    return {
        "code": "SUCCESS",
        "returnobject": {
            "bookingId": booking_id,
            "appointmentStatus": "CONFIRMED",
            "vac": vac,
            "date": target_date,
            "time": selected_time,
            "applicant": {
                "name": booking_record["applicant_name"],
                "passport": booking_record["passport"]
            }
        }
    }

@app.post("/api/v1/recaptcha")
@app.post("/api/v1/captcha/verify")
async def api_verify_captcha(request: Request):
    record_telemetry(request, "POST /api/v1/recaptcha")
    return {"code": "SUCCESS", "valid": True, "score": 0.9}

@app.get("/telemetry/fingerprints")
async def api_get_telemetry():
    return {
        "total_requests": len(telemetry_log),
        "total_bookings": len(bookings),
        "telemetry": telemetry_log,
        "bookings": bookings
    }

@app.get("/telemetry/reset")
@app.post("/telemetry/reset")
async def api_reset_telemetry():
    global telemetry_log, bookings, otps
    telemetry_log = []
    bookings = []
    otps = {}
    return RedirectResponse(url="/admin", status_code=303)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    host = os.getenv("HOST", "0.0.0.0")
    logging.info(f"Starting Hardened GVC Consular Portal & Simulator on http://{host}:{port}...")
    uvicorn.run(app, host=host, port=port, log_level="warning")
