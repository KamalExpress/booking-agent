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

@app.route('/appointments/add', methods=['POST'])
def book_appointment():
    vac = request.form.get('vac')
    type_id = request.form.get('type')
    periodslot_id = request.form.get('periodslot')
    captcha = request.form.get('g-recaptcha-response')
    
    if captcha != "LOCAL_DUMMY_TOKEN":
         return jsonify({"error": "Invalid captcha"}), 400

    print(f"\n--- BOOKING RECEIVED ---")
    print(f"Slot ID: {periodslot_id}")
    print(f"Applicant: {request.form.get('applicants[][firstname]')} {request.form.get('applicants[][surname]')}")
    print(f"Phone: {request.form.get('phonenumber')}")
    print(f"------------------------\n")
    
    # Mark the slot as unavailable
    found = False
    for slot in slots_state:
        if str(slot['id']) == str(periodslot_id):
            slot['available'] = False
            found = True
            break
            
    if not found:
        return "Slot not found or already booked", 400
        
    return "Booking Confirmed successfully!", 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)
