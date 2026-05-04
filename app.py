import os
from datetime import datetime
import json
import time
import smtplib
import re
from email.mime.text import MIMEText
from dotenv import load_dotenv 

from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import google.generativeai as genai

# ==================== LOAD ENV VARIABLES ====================
load_dotenv() 

# ==================== CONFIGURATION ====================

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'medical_robot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- EMAIL CONFIGURATION (For SOS Alerts) ---
# --- EMAIL CONFIGURATION (For SOS Alerts) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv('MAIL_USERNAME') 
SENDER_PASSWORD = os.getenv('MAIL_PASSWORD') 
# Update this line to read from .env
CAREGIVER_EMAIL = os.getenv('CAREGIVER_EMAIL', 'fallback@example.com')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

CORS(app)

# 🔴 GET API KEY
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# AI Setup
AI_AVAILABLE = False
model = None

if GOOGLE_API_KEY and "PASTE_YOUR_KEY_HERE" not in GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model = genai.GenerativeModel(m.name)
                AI_AVAILABLE = True
                print(f"✅ AI Connected: {m.name}")
                break
    except Exception as e:
        print(f"❌ AI Connection Failed: {e}")
else:
    print("⚠️  Google API Key not found or invalid in .env file.")

# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    patients = db.relationship('Patient', backref='caregiver', lazy=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    medications = db.relationship('Medication', backref='patient', lazy=True)
    room_number = db.Column(db.String(10), nullable=False)

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=30)
    
    # === NEW COLUMN: MAX STOCK (For the "60/60" logic) ===
    max_stock = db.Column(db.Integer, default=30) 

    schedule_time = db.Column(db.String(5))
    instructions = db.Column(db.String(100))
    frequency = db.Column(db.String(20), default="Daily")
    days = db.Column(db.String(50), default="All")
    last_taken = db.Column(db.String(20)) 

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    details = db.Column(db.String(200))

class UserMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    grid_data = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== HELPER FUNCTIONS ====================
def get_user_context():
    if not current_user.is_authenticated: return "No user logged in."
    context = []
    for patient in current_user.patients:
        p_info = f"PATIENT: {patient.name}\nMEDS:"
        for med in patient.medications:
            p_info += f"\n - {med.name} ({med.dosage}): Stock {med.stock}, Due {med.schedule_time}, Note: {med.instructions}"
        context.append(p_info)
    return "\n\n".join(context)

def send_emergency_email(user_name, details):
    """Sends a real email alert using SMTP"""
    try:
        if SENDER_EMAIL == 'your-project-email@gmail.com': 
            print(">> EMAIL SIMULATION: Config not set. Skipping actual send.")
            return False

        msg = MIMEText(f"URGENT ALERT: {user_name} has triggered an emergency.\n\nDetails: {details}\nTime: {datetime.now()}")
        msg['Subject'] = f"🚨 SOS ALERT - {user_name}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = CAREGIVER_EMAIL

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [CAREGIVER_EMAIL], msg.as_string())
        
        print(">> EMAIL SENT SUCCESSFULLY")
        return True
    except Exception as e:
        print(f"!! Email Failed: {e}")
        return False

# ==================== ROUTES ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Account not found.', 'error')
            return redirect(url_for('register'))
        if not check_password_hash(user.password, password):
            flash('Incorrect password.', 'error')
            return redirect(url_for('login'))
        login_user(user)
        if not user.patients: return redirect(url_for('setup'))
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username exists'); return redirect(url_for('register'))
        new_user = User(username=username, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('setup'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    if request.method == 'POST':
        data = request.json
        Patient.query.filter_by(user_id=current_user.id).delete()
        for p_data in data.get('patients', []):
            new_patient = Patient(name=p_data['name'], user_id=current_user.id)
            db.session.add(new_patient)
            db.session.commit()
            for m_data in p_data['meds']:
                new_med = Medication(
                    patient_id=new_patient.id, name=m_data['name'], dosage=m_data['dosage'],
                    # UPDATED: Initialize max_stock with initial stock
                    stock=int(m_data['stock']), max_stock=int(m_data['stock']),
                    schedule_time=m_data['time'], instructions=m_data['instructions'], 
                    frequency=m_data['frequency'], days=m_data['selected_days']
                )
                db.session.add(new_med)
        db.session.commit()
        return jsonify({'success': True, 'redirect': url_for('index')})
    return render_template('setup.html')

@app.route('/')
def landing():
    if current_user.is_authenticated: return redirect(url_for('index'))
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def index(): return render_template('index.html', user=current_user)

@app.route('/logs')
@login_required
def logs_page(): return render_template('logs.html')

@app.route('/map')
@login_required
def map_page(): return render_template('map.html')

@app.route('/history')
@login_required
def history_page():
    logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('history.html', logs=logs)

# ==================== ANALYTICS API ====================
@app.route('/api/stats')
@login_required
def get_stats():
    """Returns adherence data for charts"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    total_meds = 0
    taken_today = 0
    
    for patient in current_user.patients:
        for med in patient.medications:
            total_meds += 1
            if med.last_taken == today_str:
                taken_today += 1
    
    missed = total_meds - taken_today
    score = int((taken_today / total_meds * 100) if total_meds > 0 else 0)
    
    return jsonify({
        'total': total_meds,
        'taken': taken_today,
        'missed': missed,
        'score': score
    })

# ==================== MAP API ====================
@app.route('/api/map/save', methods=['POST'])
@login_required
def save_map():
    data = request.json
    user_map = UserMap.query.filter_by(user_id=current_user.id).first()
    if user_map: user_map.grid_data = json.dumps(data.get('grid'))
    else: db.session.add(UserMap(user_id=current_user.id, grid_data=json.dumps(data.get('grid'))))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Map Layout Saved'})

@app.route('/api/map/load')
@login_required
def load_map():
    user_map = UserMap.query.filter_by(user_id=current_user.id).first()
    if user_map: return jsonify({'success': True, 'grid': json.loads(user_map.grid_data)})
    else: return jsonify({'success': False, 'message': 'No saved map found'})

# ==================== SCHEDULE & INVENTORY API (FIXED) ====================
@app.route('/api/schedule')
@login_required
def get_schedule():
    schedule = []
    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_day = datetime.now().strftime("%a") 
    
    for patient in current_user.patients:
        for med in patient.medications:
            is_today = (med.frequency == "Daily") or (med.days and today_day in med.days)
            if is_today:
                is_done = (med.last_taken == today_str)
                status = 'completed' if is_done else ('upcoming' if med.schedule_time > now_time else 'pending')
                schedule.append({
                    "id": med.id, "day": "Today", "time": med.schedule_time,
                    "task": f"{med.name}", "patient": patient.name,
                    "type": "medicine", "status": status, "is_done": is_done
                })
    schedule.sort(key=lambda x: x['time'])
    return jsonify(schedule)

@app.route('/api/inventory')
@login_required
def get_inventory():
    inventory = []
    for patient in current_user.patients:
        for med in patient.medications:
            
            # === NEW LOGIC: CHECK FOR TODAY AND TOMORROW ===
            # We assume "Today + Tomorrow" means we need at least 2 doses available.
            status = 'ok'
            if med.stock < 2:
                status = 'low' # Logic: Not enough for today + tomorrow
            elif med.stock < 5:
                status = 'low' # Standard low warning

            # Ensure we don't divide by zero
            total = med.max_stock if med.max_stock > 0 else 30
            
            inventory.append({
                "name": f"{med.name} ({patient.name})", 
                "dosage": med.dosage,
                "stock": med.stock, 
                "total": total, # FIXED: Uses real max_stock
                "unit": "tablets",
                "status": status, 
                "instructions": med.instructions
            })
    return jsonify(inventory)

# ==================== GOLD STANDARD SYMPTOM CHECKER API ====================

# 1. Deterministic Safety Layer (Red Flags)
RED_FLAGS = ["chest pain", "shortness of breath", "numbness", "severe bleeding", "difficulty breathing", "stroke"]

def contains_emergency(text):
    return any(flag in text.lower() for flag in RED_FLAGS)

@app.route('/api/ai/symptom-check', methods=['POST'])
@login_required
def symptom_check():
    user_input = request.json.get('symptoms', '')
    
    if not AI_AVAILABLE:
        return jsonify({'success': False, 'message': "AI service currently unavailable."})

    # --- STEP 1: SAFETY CHECK ---
    if contains_emergency(user_input):
        emergency_msg = "🚨 This sounds like a medical emergency. Please stop this chat and call emergency services (911) immediately."
        # Optional: Trigger your existing email alert system
        send_emergency_email(current_user.username, f"Emergency symptoms reported: {user_input}")
        return jsonify({'success': True, 'is_emergency': True, 'response': emergency_msg})

    # --- STEP 2: HYBRID PROMPT (Grounded in context) ---
    # We include user context (meds) so the AI knows what they are already taking
    med_context = get_user_context() 
    system_instruction = f"""
    You are an expert Medical Triage Assistant. 
    CURRENT PATIENT MEDS: {med_context}
    
    INSTRUCTIONS:
    1. Start with a brief disclaimer: "I am an AI, not a doctor."
    2. Analyze the user's symptoms: "{user_input}"
    3. Look for potential interactions with their current medications listed above.
    4. Provide 2-3 possible causes, phrased strictly as possibilities.
    5. Suggest the type of doctor they should see (e.g., "You should consult a Cardiologist").
    6. If the symptoms are vague, ask 2 follow-up questions to narrow it down.
    7. Be empathetic but professional.
    """

    try:
        # Use a more capable model for reasoning if available
        global model
        response = model.generate_content(system_instruction)
        
        # --- STEP 3: LOGGING ---
        # Add a log to your ActivityLog so the caregiver sees the symptom check
        log = ActivityLog(
            user_id=current_user.id, 
            action="Symptom Check", 
            details=f"User queried: {user_input[:50]}..."
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'success': True, 
            'is_emergency': False, 
            'response': response.text
        })
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({'success': False, 'error': "The AI agent is resting. Please try again later."})

# ==================== VOICE AI API ====================
@app.route('/api/voice/process', methods=['POST'])
@login_required
def process_voice():
    user_text = request.json.get('text', '')
    if not AI_AVAILABLE: return jsonify({'success': True, 'message': "AI Missing", 'action': 'NONE'})
    
    prompt = f"""You are MediBot. SYSTEM DATA: {get_user_context()}. USER COMMAND: "{user_text}". 
    Output JSON ONLY: {{"response": "text", "action": "NONE" or "DISPENSE"}}"""
    
    try:
        res = model.generate_content(prompt)
        parsed = json.loads(res.text.replace('```json','').replace('```','').strip())
        return jsonify({'success': True, 'message': parsed['response'], 'action': parsed.get('action')})
    except: return jsonify({'success': False, 'error': "AI Error"})

# ==================== TASK OPERATIONS (FIXED) ====================
@app.route('/api/task/add', methods=['POST'])
@login_required
def add_task():
    data = request.json
    patient_id = data.get('patient_id') or current_user.patients[0].id
    new_med = Medication(
        patient_id=patient_id, name=data['name'], dosage=data.get('dosage', '1 pill'),
        # Initialize max_stock to 30 for manual adds
        stock=30, max_stock=30, 
        schedule_time=data['time'], instructions=data.get('instructions', 'Manual Add'),
        frequency="Daily", days="All"
    )
    db.session.add(new_med)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/task/delete', methods=['POST'])
@login_required
def delete_task():
    Medication.query.filter_by(id=request.json.get('id')).delete()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/task/toggle', methods=['POST'])
@login_required
def toggle_task():
    med = Medication.query.get(request.json.get('id'))
    if not med: return jsonify({'success': False})
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if med.last_taken == today_str: # UNDO
        med.last_taken = None
        # Only refund if we haven't exceeded max stock (sanity check)
        if med.stock < med.max_stock:
            med.stock += 1
        db.session.add(ActivityLog(user_id=current_user.id, action=f"Undo: {med.name}", details=f"Stock restored to {med.stock}"))
    else: # TAKE
        if med.stock > 0:
            med.last_taken = today_str
            med.stock -= 1
            db.session.add(ActivityLog(user_id=current_user.id, action=f"Dispensed {med.name}", details=f"Stock reduced to {med.stock}"))
        else: 
            return jsonify({'success': False, 'message': 'Out of Stock!'})
    
    db.session.commit()
    return jsonify({'success': True})

# ==================== EMERGENCY & REQUESTS ====================
@app.route('/api/request', methods=['POST'])
@login_required
def handle_request():
    data = request.json
    req_type = data.get('type') # 'medicine', 'water', 'help'
    
    details = "Manual Request via Dashboard"
    action_log = f"Requested {req_type.capitalize()}"
    
    if req_type == 'help':
        action_log = "EMERGENCY ALERT"
        details = "Patient pressed Panic Button. Notifying Caregiver..."
        
        email_sent = send_emergency_email(current_user.username, "Panic Button Pressed on Dashboard")
        if email_sent: details += " [Email Sent]"
        else: details += " [Email Failed]"

    new_log = ActivityLog(user_id=current_user.id, action=action_log, details=details)
    db.session.add(new_log)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{req_type} request processed'})



@app.route('/api/robot/get_state')
def get_robot_state():
    return jsonify(robot_state)

# ==================== SEEDING (UPDATED) ====================
@app.route('/seed_full_day')
@login_required
def seed_full_day():
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        patient = Patient(name="Grandpa Joe", user_id=current_user.id)
        db.session.add(patient); db.session.commit()

    schedule_data = [
        {"name": "Omeprazole", "dosage": "20mg", "time": "08:00", "instructions": "Stomach Protector", "stock": 28, "max": 30},
        {"name": "Metformin", "dosage": "500mg", "time": "08:00", "instructions": "Diabetes", "stock": 60, "max": 60},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "08:00", "instructions": "Antibiotic", "stock": 21, "max": 21},
        {"name": "Aspirin", "dosage": "75mg", "time": "08:00", "instructions": "Heart Health", "stock": 30, "max": 30},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "13:00", "instructions": "Antibiotic Dose 2", "stock": 21, "max": 21},
        {"name": "Vitamin D3", "dosage": "1000 IU", "time": "13:00", "instructions": "Bone Supplement", "stock": 90, "max": 90},
        {"name": "Metformin", "dosage": "500mg", "time": "20:00", "instructions": "Diabetes Evening", "stock": 60, "max": 60},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "20:00", "instructions": "Antibiotic Dose 3", "stock": 21, "max": 21},
        {"name": "Atorvastatin", "dosage": "20mg", "time": "20:00", "instructions": "Cholesterol", "stock": 30, "max": 30}
    ]

    added = 0
    for item in schedule_data:
        # Check if already exists to prevent duplicate seeding
        if not Medication.query.filter_by(name=item['name'], schedule_time=item['time'], patient_id=patient.id).first():
            db.session.add(Medication(
                patient_id=patient.id, name=item['name'], dosage=item['dosage'], 
                stock=item['stock'], max_stock=item['max'], # SAVE MAX
                schedule_time=item['time'], instructions=item['instructions'], 
                frequency="Daily", days="All", last_taken=None
            ))
            added += 1
    db.session.commit()

    return f"""<div style="font-family:sans-serif;text-align:center;padding:50px;background:#111;color:white;">
    <h1 style="color:#48bb78;">✓ System Seeded</h1><p>Added {added} complex medications.</p>
    <a href='/dashboard' style="background:#0a84ff;color:white;padding:15px;text-decoration:none;border-radius:20px;">Back to Dashboard</a></div>"""
# ==================== ROBOT API (NO LOGIN REQUIRED) ====================

@app.route('/api/robot/check/<int:user_id>')
def robot_check_schedule(user_id):
    """
    The robot calls this to see if there are PENDING tasks right now.
    We pass user_id manually because there is no logged-in user session.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    due_tasks = []
    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_day = datetime.now().strftime("%a")

    for patient in user.patients:
        for med in patient.medications:
            # 1. Check if it's the right day
            if (med.frequency == "Daily") or (med.days and today_day in med.days):
                # 2. Check if already taken today
                if med.last_taken != today_str:
                    # 3. Check if it is TIME (or past time)
                    if med.schedule_time <= now_time:
                        # Found a task that is DUE and NOT TAKEN
                      due_tasks.append({
                            "med_id": med.id,
                            "medicine": med.name,
                            "dosage": med.dosage,
                            "patient": patient.name,
                            "room": patient.room_number   # ✅ dynamic room mapping
                        })
    
    return jsonify(due_tasks)

@app.route('/api/robot/complete', methods=['POST'])
def robot_mark_complete():
    """
    Robot calls this to mark a pill as dispensed.
    """
    data = request.json
    med_id = data.get('med_id')
    med = Medication.query.get(med_id)
    
    if med:
        # Mark as taken for today
        med.last_taken = datetime.now().strftime("%Y-%m-%d")
        
        # Decrease stock
        if med.stock > 0:
            med.stock -= 1
            
        # Log it
        # Note: We hardcode user_id=1 or find it via patient because we don't have current_user
        log = ActivityLog(user_id=med.patient.user_id, action=f"Robot Dispensed {med.name}", details="Auto-dispensed by Pi")
        db.session.add(log)
        db.session.commit()
        return jsonify({"success": True})
        
    return jsonify({"success": False}), 400


# ==================== RUN APP ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Host 0.0.0.0 makes it accessible to other devices (Laptop/Mobile)
    app.run(host='0.0.0.0', port=5000, debug=True)