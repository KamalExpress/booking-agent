import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv

# Load environment variables from the root .env file
root_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(root_env)

app = Flask(__name__)

@app.route('/dist/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('styles', filename)

@app.route('/dist/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('js', filename)

# Stateful memory for available slots
slots_state = []
num_slots = int(os.getenv('AVAILABLE_SLOTS', '5'))
for i in range(1, num_slots + 1):
    hour = 9 + (i // 2)
    minute = "30" if i % 2 != 0 else "00"
    time_str = f"{hour:02d}:{minute}"
    slots_state.append({"id": i, "date": "09/07/2026", "time": time_str, "available": True})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/anonymous/home', methods=['GET'])
def anonymous_home():
    return jsonify({"status": "ok"}), 200

@app.route('/api/v1/translations', methods=['GET'])
def translations():
    import json
    try:
        with open('translations.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": "Translations not found"}), 404

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400
        
    username = data.get('username')
    password = data.get('password')
    captcha = data.get('g-recaptcha-response')
    
    # Mock validation
    if captcha == "LOCAL_DUMMY_TOKEN" and username and password:
        return jsonify({"message": "Login successful", "token": "fake-jwt-token"}), 200
    else:
        return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/v1/periodslot/slots', methods=['PUT'])
def search_slots():
    # app.js expects a specific nested structure
    req_data = request.get_json() or {}
    date_from = req_data.get('datefrom', '09/07/2026')
    
    matching_slots = []
    for s in slots_state:
        if s['date'] == date_from:
            matching_slots.append({
                "id": s['id'],
                "starttime": s['time'],
                "isavailable": s['available'],
                "isselectable": s['available'],
                "numofavailableslots": 1 if s['available'] else 0
            })
            
    return jsonify({
        "code": "SUCCESS",
        "returnobject": {
            "slots": matching_slots
        }
    }), 200

@app.route('/appointments/add', methods=['GET', 'POST'])
def appointments_add():
    # Return HTML containing hidden otpuser
    html = """
    <div>
      <h1><span>My Appointments | Add</span></h1>
      <form id="appointment" class="classic" onsubmit="return false">
        <input type="hidden" name="otpuser" id="otpuser" value="User{id=931995, username=test@kamal.com, firstname=TEST, vac=Vac{id=138}}"/>
      </form>
    </div>
    """
    return html, 200

@app.route('/api/v1/onetimepassword/sendOtpBookAppointment/<phone>/<prefix_id>', methods=['POST'])
def send_otp_book_appointment(phone, prefix_id):
    print(f"\n[MockPortal] OTP SMS triggered for Phone: +{prefix_id}-{phone}")
    return jsonify({"message": "OTP code sent by SMS", "returnobject": None, "code": "SUCCESS"}), 200

@app.route('/api/v1/appointments', methods=['POST'])
def api_appointments():
    data = request.get_json() or {}
    print(f"\n--- [MockPortal] BOOKING JSON RECEIVED ---")
    print(f"VAC: {data.get('vac')}")
    print(f"OTP: {data.get('onetimepassword')}")
    print(f"Applicants: {data.get('applicants')}")
    print(f"Selected Time: {data.get('selectedtime')}")
    print(f"-----------------------------------------\n")
    
    # Check OTP
    otp = str(data.get('onetimepassword', ''))
    if len(otp) < 4:
        return jsonify({"message": "Mismatch OTP. Please, try again", "returnobject": None, "code": "INVALID"}), 200
        
    ref_code = f"GVCW-PK-ISB-{int(time.time())}"
    return jsonify({
        "message": "Success",
        "returnobject": {
            "reference": ref_code,
            "appointmentId": 2528256,
            "status": "CONFIRMED"
        },
        "code": "SUCCESS"
    }), 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)
