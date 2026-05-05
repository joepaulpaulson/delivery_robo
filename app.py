import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_cors import CORS
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

import google.generativeai as genai


load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir, "database", "medical_robot.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("MAIL_USERNAME")
SENDER_PASSWORD = os.getenv("MAIL_PASSWORD")
CAREGIVER_EMAIL = os.getenv("CAREGIVER_EMAIL", "fallback@example.com")

ROOM_PATTERN = re.compile(r"^[A-Z]-\d{3}$")
ROOM_SEARCH_PATTERN = re.compile(r"\b([A-Za-z]-\d{3})\b")
ROBOT_COMMANDS = {
    "forward",
    "backward",
    "left",
    "right",
    "stop",
    "dock",
    "emergency",
    "open_drawer",
    "close_drawer",
}
DEFAULT_MAP_PAYLOAD = {"grid": [], "rooms": {}, "base": {"x": 2, "y": 2}}
GRID_STEP_SECONDS = 4

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
CORS(app)


try:
    from hardware.camera_stream import camera as camera_service

    CAMERA_SERVICE_AVAILABLE = True
except Exception as camera_error:  # pragma: no cover - hardware import fallback
    camera_service = None
    CAMERA_SERVICE_AVAILABLE = False
    print(f"Camera service unavailable: {camera_error}")


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AI_AVAILABLE = False
model = None

if GOOGLE_API_KEY and "PASTE_YOUR_KEY_HERE" not in GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        for available_model in genai.list_models():
            if "generateContent" in available_model.supported_generation_methods:
                model = genai.GenerativeModel(available_model.name)
                AI_AVAILABLE = True
                print(f"AI connected: {available_model.name}")
                break
    except Exception as ai_error:
        print(f"AI connection failed: {ai_error}")
else:
    print("Google API key not configured.")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    patients = db.relationship("Patient", backref="caregiver", lazy=True)


class Account(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    username = db.Column(db.String(150), unique=True, nullable=True)
    password = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), unique=True, nullable=True)

    admin_user = db.relationship("User", foreign_keys=[user_id])
    patient = db.relationship("Patient", foreign_keys=[patient_id], back_populates="account")

    @property
    def display_name(self):
        if self.role == "ADMIN":
            return self.email or (self.admin_user.username if self.admin_user else "Admin")
        return self.username or (self.patient.name if self.patient else "Patient")


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(30), nullable=True)
    room_number = db.Column(db.String(10), nullable=False, default="A-101")
    bed_number = db.Column(db.String(20), nullable=True)
    emergency_notes = db.Column(db.String(200), nullable=True)
    medications = db.relationship("Medication", backref="patient", lazy=True)
    account = db.relationship("Account", back_populates="patient", uselist=False)


class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=30)
    max_stock = db.Column(db.Integer, default=30)
    schedule_time = db.Column(db.String(5))
    instructions = db.Column(db.String(100))
    frequency = db.Column(db.String(20), default="Daily")
    days = db.Column(db.String(50), default="All")
    last_taken = db.Column(db.String(20))


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    details = db.Column(db.String(200))


class PatientHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    created_by_account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    entry_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    details = db.Column(db.String(300), nullable=True)
    symptom_name = db.Column(db.String(100), nullable=True)
    improvement_percent = db.Column(db.Integer, nullable=True)
    pain_level = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=True)
    request_task_id = db.Column(db.Integer, db.ForeignKey("robot_task.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    patient = db.relationship("Patient", foreign_keys=[patient_id])
    created_by_account = db.relationship("Account", foreign_keys=[created_by_account_id])
    medication = db.relationship("Medication", foreign_keys=[medicine_id])


class UserMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    grid_data = db.Column(db.Text, nullable=False)


class RobotState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    battery_level = db.Column(db.Integer, default=100)
    location = db.Column(db.String(100), default="Dock")
    is_moving = db.Column(db.Boolean, default=False)
    wifi_signal = db.Column(db.Integer, default=4)
    drawer_open = db.Column(db.Boolean, default=False)
    current_task = db.Column(db.String(120), default="Idle")
    heart_rate = db.Column(db.Integer, default=72)
    spo2 = db.Column(db.Integer, default=98)
    temperature = db.Column(db.Float, default=36.7)
    bluetooth_connected = db.Column(db.Boolean, default=True)
    camera_available = db.Column(db.Boolean, default=CAMERA_SERVICE_AVAILABLE)
    privacy_mode = db.Column(db.Boolean, default=False)
    current_stop_index = db.Column(db.Integer, default=0)
    remaining_stops = db.Column(db.Integer, default=0)
    estimated_remaining_seconds = db.Column(db.Integer, default=0)
    last_heartbeat = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class RobotTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=True)
    medication_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=True)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="queued")
    source = db.Column(db.String(20), default="dashboard")
    priority = db.Column(db.Integer, default=100)
    room_number = db.Column(db.String(10))
    payload = db.Column(db.Text, default="{}")
    response_message = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    claimed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)

    patient = db.relationship("Patient", foreign_keys=[patient_id])
    medication = db.relationship("Medication", foreign_keys=[medication_id])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Account, int(user_id))


def ensure_legacy_schema():
    db.create_all()

    patient_columns = {
        row["name"]
        for row in db.session.execute(text("PRAGMA table_info(patient)")).mappings().all()
    }
    medication_columns = {
        row["name"]
        for row in db.session.execute(text("PRAGMA table_info(medication)")).mappings().all()
    }
    user_columns = {
        row["name"]
        for row in db.session.execute(text("PRAGMA table_info(user)")).mappings().all()
    }
    robot_state_columns = {
        row["name"]
        for row in db.session.execute(text("PRAGMA table_info(robot_state)")).mappings().all()
    }

    if "room_number" not in patient_columns:
        db.session.execute(
            text(
                "ALTER TABLE patient ADD COLUMN room_number VARCHAR(10) DEFAULT 'A-101'"
            )
        )
    if "age" not in patient_columns:
        db.session.execute(text("ALTER TABLE patient ADD COLUMN age INTEGER"))
    if "gender" not in patient_columns:
        db.session.execute(text("ALTER TABLE patient ADD COLUMN gender VARCHAR(30)"))
    if "bed_number" not in patient_columns:
        db.session.execute(text("ALTER TABLE patient ADD COLUMN bed_number VARCHAR(20)"))
    if "emergency_notes" not in patient_columns:
        db.session.execute(text("ALTER TABLE patient ADD COLUMN emergency_notes VARCHAR(200)"))
    if "max_stock" not in medication_columns:
        db.session.execute(
            text("ALTER TABLE medication ADD COLUMN max_stock INTEGER DEFAULT 30")
        )
    if "password" not in user_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN password VARCHAR(150)"))
    if "current_stop_index" not in robot_state_columns:
        db.session.execute(
            text("ALTER TABLE robot_state ADD COLUMN current_stop_index INTEGER DEFAULT 0")
        )
    if "remaining_stops" not in robot_state_columns:
        db.session.execute(
            text("ALTER TABLE robot_state ADD COLUMN remaining_stops INTEGER DEFAULT 0")
        )
    if "estimated_remaining_seconds" not in robot_state_columns:
        db.session.execute(
            text(
                "ALTER TABLE robot_state ADD COLUMN estimated_remaining_seconds INTEGER DEFAULT 0"
            )
        )

    db.session.execute(
        text(
            "UPDATE patient SET room_number = COALESCE(NULLIF(room_number, ''), 'A-101')"
        )
    )
    db.session.execute(
        text("UPDATE medication SET max_stock = COALESCE(max_stock, stock, 30)")
    )
    db.session.execute(
        text(
            "UPDATE robot_state SET "
            "current_stop_index = COALESCE(current_stop_index, 0), "
            "remaining_stops = COALESCE(remaining_stops, 0), "
            "estimated_remaining_seconds = COALESCE(estimated_remaining_seconds, 0)"
        )
    )
    db.session.commit()
    bootstrap_accounts()


def bootstrap_accounts():
    changed = False
    for user in User.query.all():
        existing_account = Account.query.filter_by(user_id=user.id, role="ADMIN").first()
        if existing_account:
            continue
        admin_account = Account(
            role="ADMIN",
            email=user.username,
            username=None,
            password=user.password,
            user_id=user.id,
        )
        db.session.add(admin_account)
        changed = True

    if changed:
        db.session.commit()


def normalize_room_number(room_number):
    return (room_number or "").strip().upper()


def validate_room_number(room_number):
    return bool(ROOM_PATTERN.match(normalize_room_number(room_number)))


def current_account():
    if current_user.is_authenticated and isinstance(current_user, Account):
        return current_user
    return None


def current_admin_user():
    account = current_account()
    if not account:
        return None
    if account.role == "ADMIN":
        return account.admin_user
    if account.role == "PATIENT" and account.patient:
        return account.patient.caregiver
    return None


def current_patient_profile():
    account = current_account()
    if account and account.role == "PATIENT":
        return account.patient
    return None


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_account() or current_account().role != "ADMIN":
            flash("Admin access only.", "error")
            if current_account() and current_account().role == "PATIENT":
                return redirect(url_for("patient_dashboard"))
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def patient_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("patient_login"))
        if not current_account() or current_account().role != "PATIENT":
            flash("Patient access only.", "error")
            if current_account() and current_account().role == "ADMIN":
                return redirect(url_for("index"))
            return redirect(url_for("patient_login"))
        return view_func(*args, **kwargs)

    return wrapped


def patient_account_for_patient(patient):
    if not patient:
        return None
    return Account.query.filter_by(patient_id=patient.id, role="PATIENT").first()


def admin_account_for_user(user):
    if not user:
        return None
    return Account.query.filter_by(user_id=user.id, role="ADMIN").first()


def get_alert_email_for_user(user):
    admin_account = admin_account_for_user(user)
    return (admin_account.email if admin_account and admin_account.email else None) or CAREGIVER_EMAIL


def get_user_context(user=None, patient=None):
    if not user and not patient:
        user = current_admin_user()
        patient = current_patient_profile()

    if not user and not patient:
        return "No user logged in."

    context = []
    patients = [patient] if patient else list(user.patients)
    for patient_item in patients:
        patient_info = [f"PATIENT: {patient_item.name} ({patient_item.room_number})", "MEDS:"]
        for med in patient_item.medications:
            patient_info.append(
                f" - {med.name} ({med.dosage}): Stock {med.stock}, Due {med.schedule_time}, Note: {med.instructions}"
            )
        context.append("\n".join(patient_info))
    return "\n\n".join(context)


def send_emergency_email(user_name, details, recipient_email=None):
    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            print("Email configuration missing. Skipping email send.")
            return False

        destination_email = recipient_email or CAREGIVER_EMAIL

        msg = MIMEText(
            f"URGENT ALERT: {user_name} triggered an emergency.\n\nDetails: {details}\nTime: {datetime.now()}"
        )
        msg["Subject"] = f"SOS ALERT - {user_name}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = destination_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [destination_email], msg.as_string())
        return True
    except Exception as email_error:
        print(f"Email failed: {email_error}")
        return False


def create_activity(user_id, action, details):
    db.session.add(ActivityLog(user_id=user_id, action=action, details=details))


def create_patient_history(
    patient,
    entry_type,
    title,
    *,
    details=None,
    symptom_name=None,
    improvement_percent=None,
    pain_level=None,
    temperature=None,
    medication=None,
    request_task=None,
    created_by_account=None,
):
    if not patient:
        return None

    history_entry = PatientHistory(
        patient_id=patient.id,
        created_by_account_id=created_by_account.id if created_by_account else None,
        entry_type=entry_type,
        title=title[:120],
        details=(details or "")[:300] or None,
        symptom_name=(symptom_name or "")[:100] or None,
        improvement_percent=improvement_percent,
        pain_level=pain_level,
        temperature=temperature,
        medicine_id=medication.id if medication else None,
        request_task_id=request_task.id if request_task else None,
    )
    db.session.add(history_entry)
    return history_entry


def serialize_patient_history(entry):
    author = "System"
    if entry.created_by_account:
        author = "Caretaker" if entry.created_by_account.role == "ADMIN" else "Patient"

    return {
        "id": entry.id,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "details": entry.details,
        "symptom_name": entry.symptom_name,
        "improvement_percent": entry.improvement_percent,
        "pain_level": entry.pain_level,
        "temperature": entry.temperature,
        "medicine_name": entry.medication.name if entry.medication else None,
        "author": author,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def parse_map_payload(user_map):
    if not user_map:
        return DEFAULT_MAP_PAYLOAD.copy()

    try:
        raw_payload = json.loads(user_map.grid_data)
    except (TypeError, json.JSONDecodeError):
        return DEFAULT_MAP_PAYLOAD.copy()

    if isinstance(raw_payload, list):
        return {
            "grid": raw_payload,
            "rooms": {},
            "base": DEFAULT_MAP_PAYLOAD["base"].copy(),
        }

    if not isinstance(raw_payload, dict):
        return DEFAULT_MAP_PAYLOAD.copy()

    grid = raw_payload.get("grid")
    rooms = raw_payload.get("rooms", {})
    base = raw_payload.get("base", DEFAULT_MAP_PAYLOAD["base"])

    if not isinstance(grid, list):
        grid = []
    if not isinstance(rooms, dict):
        rooms = {}
    if not isinstance(base, dict):
        base = DEFAULT_MAP_PAYLOAD["base"].copy()

    return {"grid": grid, "rooms": rooms, "base": base}


def save_map_payload(user_id, payload):
    serialized = json.dumps(payload)
    user_map = UserMap.query.filter_by(user_id=user_id).first()
    if user_map:
        user_map.grid_data = serialized
    else:
        user_map = UserMap(user_id=user_id, grid_data=serialized)
        db.session.add(user_map)
    return user_map


def get_or_create_robot_state(user_id):
    state = RobotState.query.filter_by(user_id=user_id).first()
    if state:
        return state

    state = RobotState(user_id=user_id)
    db.session.add(state)
    db.session.commit()
    return state


def serialize_robot_state(state):
    return {
        "battery_level": state.battery_level,
        "location": state.location,
        "is_moving": state.is_moving,
        "wifi_signal": state.wifi_signal,
        "drawer_open": state.drawer_open,
        "current_task": state.current_task,
        "heart_rate": state.heart_rate,
        "spo2": state.spo2,
        "temperature": state.temperature,
        "bluetooth_connected": state.bluetooth_connected,
        "camera_available": state.camera_available,
        "privacy_mode": state.privacy_mode,
        "current_stop_index": state.current_stop_index,
        "remaining_stops": state.remaining_stops,
        "estimated_remaining_seconds": state.estimated_remaining_seconds,
        "last_update": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
    }


def get_primary_patient(user):
    if not user.patients:
        return None

    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_day = datetime.now().strftime("%a")

    for patient in user.patients:
        for med in patient.medications:
            is_due_today = med.frequency == "Daily" or (med.days and today_day in med.days)
            if is_due_today and med.last_taken != today_str and med.schedule_time <= now_time:
                return patient
    return user.patients[0]


def get_owned_patient(patient_id):
    admin_user = current_admin_user()
    if patient_id is None:
        return None
    if not admin_user:
        return None
    return Patient.query.filter_by(id=patient_id, user_id=admin_user.id).first()


def get_owned_medication(medication_id):
    admin_user = current_admin_user()
    if not admin_user:
        return None
    return (
        Medication.query.join(Patient, Medication.patient_id == Patient.id)
        .filter(Medication.id == medication_id, Patient.user_id == admin_user.id)
        .first()
    )


def queue_robot_task(
    user_id,
    task_type,
    *,
    patient=None,
    medication=None,
    room_number=None,
    payload=None,
    priority=100,
    source="dashboard",
    response_message=None,
):
    task = RobotTask(
        user_id=user_id,
        patient_id=patient.id if patient else None,
        medication_id=medication.id if medication else None,
        task_type=task_type,
        status="queued",
        source=source,
        priority=priority,
        room_number=room_number,
        payload=json.dumps(payload or {}),
        response_message=response_message,
    )
    db.session.add(task)
    return task


def serialize_robot_task(task):
    try:
        payload = json.loads(task.payload or "{}")
    except json.JSONDecodeError:
        payload = {}

    patient_name = None
    if task.patient:
        patient_name = task.patient.name
    elif task.medication and task.medication.patient:
        patient_name = task.medication.patient.name
    else:
        patient_name = payload.get("patient_name")

    return {
        "id": task.id,
        "source_type": "robot_task",
        "task_type": task.task_type,
        "status": task.status,
        "source": task.source,
        "priority": task.priority,
        "room": task.room_number,
        "message": task.response_message,
        "patient": patient_name,
        "payload": payload,
        "medication": task.medication.name if task.medication else payload.get("medication"),
        "dosage": task.medication.dosage if task.medication else payload.get("dosage"),
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def schedule_payload_for_user(user):
    schedule = []
    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_day = datetime.now().strftime("%a")

    for patient in user.patients:
        for med in patient.medications:
            is_today = med.frequency == "Daily" or (med.days and today_day in med.days)
            if not is_today:
                continue

            is_done = med.last_taken == today_str
            status = "completed" if is_done else ("pending" if med.schedule_time <= now_time else "upcoming")
            schedule.append(
                {
                    "id": med.id,
                    "day": "Today",
                    "time": med.schedule_time,
                    "task": med.name,
                    "patient": patient.name,
                    "room_number": patient.room_number,
                    "type": "medicine",
                    "status": status,
                    "is_done": is_done,
                    "dosage": med.dosage,
                    "notes": med.instructions,
                }
            )

    schedule.sort(key=lambda item: item["time"])
    return schedule


def today_schedule_api_payload(user):
    items = []
    for item in schedule_payload_for_user(user):
        normalized_status = item["status"]
        if normalized_status == "upcoming":
            normalized_status = "pending"
        items.append(
            {
                "id": item["id"],
                "time": f"{datetime.now().strftime('%Y-%m-%d')} {item['time']}",
                "task": item["task"],
                "status": normalized_status,
                "notes": item["notes"],
                "dosage": item["dosage"],
            }
        )
    return items


def stats_payload_for_user(user):
    today_str = datetime.now().strftime("%Y-%m-%d")
    total = 0
    taken = 0

    for patient in user.patients:
        for med in patient.medications:
            total += 1
            if med.last_taken == today_str:
                taken += 1

    missed = max(total - taken, 0)
    score = int((taken / total) * 100) if total else 0

    request_counts = {"queued": 0, "dispatched": 0, "completed": 0, "failed": 0}
    for status, count in (
        db.session.query(RobotTask.status, db.func.count(RobotTask.id))
        .filter(RobotTask.user_id == user.id)
        .group_by(RobotTask.status)
        .all()
    ):
        request_counts[status] = count

    return {
        "total": total,
        "taken": taken,
        "missed": missed,
        "score": score,
        "requests": request_counts,
    }


def stats_payload_for_patient(patient):
    today_str = datetime.now().strftime("%Y-%m-%d")
    total = len(patient.medications)
    taken = sum(1 for med in patient.medications if med.last_taken == today_str)
    missed = max(total - taken, 0)
    score = int((taken / total) * 100) if total else 0
    request_counts = {"queued": 0, "dispatched": 0, "completed": 0, "failed": 0}
    for status, count in (
        db.session.query(RobotTask.status, db.func.count(RobotTask.id))
        .filter(RobotTask.patient_id == patient.id)
        .group_by(RobotTask.status)
        .all()
    ):
        request_counts[status] = count

    return {
        "total": total,
        "taken": taken,
        "missed": missed,
        "score": score,
        "requests": request_counts,
    }


def patient_history_entries(patient, limit=None):
    query = PatientHistory.query.filter_by(patient_id=patient.id).order_by(PatientHistory.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def serialize_recent_patient_requests(patient, limit=10):
    tasks = (
        RobotTask.query.filter_by(patient_id=patient.id)
        .order_by(RobotTask.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    label_map = {
        "medicine_delivery": "Medicine",
        "water_delivery": "Water",
        "help_request": "SOS",
        "room_navigation": "Navigation",
        "robot_command": "Robot Command",
    }
    for task in tasks:
        items.append(
            {
                "id": task.id,
                "label": label_map.get(task.task_type, task.task_type.replace("_", " ").title()),
                "status": task.status.title(),
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "message": task.response_message,
            }
        )
    return items


def create_request_for_patient(patient, request_type, *, source="dashboard", created_by_account=None):
    owner_user = patient.caregiver if patient else None
    resolved_room = normalize_room_number(patient.room_number if patient else "")
    if not validate_room_number(resolved_room):
        return None, "Complete patient setup with a valid room before sending robot requests."

    task_map = {
        "medicine": ("medicine_delivery", 30, "Medication assistance queued."),
        "water": ("water_delivery", 40, "Water delivery queued."),
        "help": ("help_request", 5, "Emergency assistance queued."),
    }
    task_type, priority, message = task_map[request_type]

    payload = {
        "request_type": request_type,
        "patient_name": patient.name if patient else (owner_user.username if owner_user else "Patient"),
        "room_number": resolved_room,
    }
    task = queue_robot_task(
        owner_user.id,
        task_type,
        patient=patient,
        room_number=resolved_room,
        payload=payload,
        priority=priority,
        source=source,
        response_message=message,
    )

    action = "EMERGENCY ALERT" if request_type == "help" else f"Requested {request_type.capitalize()}"
    details = f"{request_type.capitalize()} request queued for {patient.name} in room {resolved_room}."
    if request_type == "help":
        email_sent = send_emergency_email(
            patient.name,
            f"SOS request for room {resolved_room}",
            recipient_email=get_alert_email_for_user(owner_user),
        )
        details += " Caregiver notified." if email_sent else " Caregiver notification failed."
    create_activity(owner_user.id, action, details)

    entry_type = {
        "medicine": "medicine_requested",
        "water": "water_requested",
        "help": "sos_alert",
    }[request_type]
    create_patient_history(
        patient,
        entry_type,
        title=f"{request_type.capitalize()} requested",
        details=details,
        request_task=task,
        created_by_account=created_by_account,
    )
    return task, message


def create_dashboard_request(user, request_type, source="dashboard", room_number=None, created_by_account=None):
    primary_patient = get_primary_patient(user)
    if room_number:
        normalized_room = normalize_room_number(room_number)
        explicit_patient = next(
            (patient for patient in user.patients if normalize_room_number(patient.room_number) == normalized_room),
            None,
        )
        if explicit_patient:
            primary_patient = explicit_patient
    if not primary_patient:
        return None, "Complete patient setup with a valid room before sending robot requests."
    return create_request_for_patient(
        primary_patient,
        request_type,
        source=source,
        created_by_account=created_by_account,
    )


def queue_robot_command_for_user(user_id, command, source="dashboard"):
    state = get_or_create_robot_state(user_id)
    priority = 1 if command == "emergency" else 15
    message = f"Robot command '{command}' queued."
    task = queue_robot_task(
        user_id,
        "robot_command",
        room_number=None,
        payload={"command": command},
        priority=priority,
        source=source,
        response_message=message,
    )
    state.current_task = f"Queued: {command}"
    state.updated_at = datetime.now()
    return task, message


def create_navigation_task(user, room_number, source):
    normalized_room = normalize_room_number(room_number)
    if not validate_room_number(normalized_room):
        return None, "Use a valid room number like A-101."

    map_payload = parse_map_payload(UserMap.query.filter_by(user_id=user.id).first())
    if normalized_room not in map_payload["rooms"]:
        return None, f"Room {normalized_room} is not mapped yet."

    task = queue_robot_task(
        user.id,
        "room_navigation",
        room_number=normalized_room,
        payload={"room_number": normalized_room},
        priority=20,
        source=source,
        response_message=f"Navigation to {normalized_room} queued.",
    )
    create_activity(user.id, "Queued Navigation", f"Robot navigation queued for room {normalized_room}.")
    return task, f"Navigation to {normalized_room} queued."


def interpret_command_text(user, command_text, source, *, allow_robot_commands=True, created_by_account=None):
    text_value = (command_text or "").strip()
    if not text_value:
        return {"success": False, "message": "Please enter a command."}

    lower_text = text_value.lower()
    room_match = ROOM_SEARCH_PATTERN.search(text_value)
    room_number = normalize_room_number(room_match.group(1)) if room_match else None

    if any(keyword in lower_text for keyword in ["sos", "panic", "emergency", "help me"]):
        task, message = create_dashboard_request(
            user,
            "help",
            source=source,
            room_number=room_number,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "HELP", "task_id": task.id}

    if "water" in lower_text:
        task, message = create_dashboard_request(
            user,
            "water",
            source=source,
            room_number=room_number,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "WATER", "task_id": task.id}

    if any(keyword in lower_text for keyword in ["medicine", "medication", "pill", "tablet", "dispense"]):
        task, message = create_dashboard_request(
            user,
            "medicine",
            source=source,
            room_number=room_number,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "MEDICINE", "task_id": task.id}

    if room_number and any(keyword in lower_text for keyword in ["go to", "navigate", "move to", "visit"]):
        task, message = create_navigation_task(user, room_number, source)
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "NAVIGATE", "task_id": task.id}

    command_map = {
        "return to dock": "dock",
        "go home": "dock",
        "dock": "dock",
        "stop": "stop",
        "halt": "stop",
    }
    if allow_robot_commands:
        command_map.update(
            {
                "open drawer": "open_drawer",
                "close drawer": "close_drawer",
                "forward": "forward",
                "backward": "backward",
                "left": "left",
                "right": "right",
            }
        )

    for phrase, command in command_map.items():
        if phrase in lower_text:
            task, message = queue_robot_command_for_user(user.id, command, source=source)
            create_activity(user.id, "Queued Robot Command", message)
            return {"success": True, "message": message, "action": command.upper(), "task_id": task.id}

    return {
        "success": False,
        "message": (
            "Command not recognized. Try water, medicine, SOS, or return robot."
            if not allow_robot_commands
            else "Command not recognized. Try water, medicine, SOS, dock, stop, or go to room A-101."
        ),
    }


def interpret_patient_command_text(patient, command_text, source, *, created_by_account=None):
    text_value = (command_text or "").strip()
    if not text_value:
        return {"success": False, "message": "Please enter a command."}

    lower_text = text_value.lower()
    if any(keyword in lower_text for keyword in ["sos", "panic", "emergency", "help me", "call caretaker"]):
        task, message = create_request_for_patient(
            patient,
            "help",
            source=source,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "HELP", "task_id": task.id}

    if "water" in lower_text:
        task, message = create_request_for_patient(
            patient,
            "water",
            source=source,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "WATER", "task_id": task.id}

    if any(keyword in lower_text for keyword in ["medicine", "medication", "pill", "tablet"]):
        task, message = create_request_for_patient(
            patient,
            "medicine",
            source=source,
            created_by_account=created_by_account,
        )
        if not task:
            return {"success": False, "message": message}
        return {"success": True, "message": message, "action": "MEDICINE", "task_id": task.id}

    if any(keyword in lower_text for keyword in ["return robot", "send robot back", "go home", "dock", "return to dock"]):
        task, message = queue_robot_command_for_user(patient.user_id, "dock", source=source)
        create_activity(patient.user_id, "Patient Requested Dock", f"{patient.name} asked the robot to return to dock.")
        return {"success": True, "message": message, "action": "DOCK", "task_id": task.id}

    return {"success": False, "message": "Command not recognized. Try water, medicine, SOS, or return robot."}


def contains_emergency(text_value):
    red_flags = [
        "chest pain",
        "shortness of breath",
        "numbness",
        "severe bleeding",
        "difficulty breathing",
        "stroke",
    ]
    return any(flag in text_value.lower() for flag in red_flags)


def next_queued_robot_task(user_id):
    task = (
        RobotTask.query.filter_by(user_id=user_id, status="queued")
        .order_by(RobotTask.priority.asc(), RobotTask.created_at.asc())
        .first()
    )
    if task:
        task.status = "dispatched"
        task.claimed_at = datetime.now()
        state = get_or_create_robot_state(user_id)
        state.current_task = task.task_type
        state.is_moving = task.task_type != "robot_command"
        state.updated_at = datetime.now()
        db.session.commit()
        return serialize_robot_task(task)
    return None


def collect_due_medication_tasks(user):
    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_day = datetime.now().strftime("%a")

    due_tasks = []
    for patient in user.patients:
        for med in patient.medications:
            is_today = med.frequency == "Daily" or (med.days and today_day in med.days)
            if not is_today or med.last_taken == today_str or med.schedule_time > now_time:
                continue
            due_tasks.append(
                {
                    "med_id": med.id,
                    "medicine": med.name,
                    "dosage": med.dosage,
                    "patient": patient.name,
                    "room": patient.room_number,
                    "time": med.schedule_time,
                    "patient_id": patient.id,
                }
            )

    due_tasks.sort(key=lambda item: (item["time"], item["med_id"]))
    return due_tasks


def group_tasks_by_room(tasks):
    grouped = {}
    for task in tasks:
        room_number = normalize_room_number(task["room"])
        room_entry = grouped.setdefault(
            room_number,
            {
                "room": room_number,
                "patient_deliveries": [],
            },
        )
        room_entry["patient_deliveries"].append(
            {
                "med_id": task["med_id"],
                "medicine": task["medicine"],
                "dosage": task["dosage"],
                "patient": task["patient"],
                "patient_id": task["patient_id"],
                "scheduled_time": task["time"],
            }
        )
    return grouped


def map_neighbors(point, cols, rows):
    x, y = point
    neighbors = []
    if x < cols - 1:
        neighbors.append((x + 1, y))
    if x > 0:
        neighbors.append((x - 1, y))
    if y < rows - 1:
        neighbors.append((x, y + 1))
    if y > 0:
        neighbors.append((x, y - 1))
    return neighbors


def find_map_path(grid, start, goal):
    cols = len(grid)
    rows = len(grid[0]) if cols else 0
    if not cols or not rows:
        return []

    if not (0 <= start[0] < cols and 0 <= start[1] < rows):
        return []
    if not (0 <= goal[0] < cols and 0 <= goal[1] < rows):
        return []

    open_set = [{"point": start, "g": 0, "h": 0, "f": 0, "parent": None}]
    closed = set()

    while open_set:
        current_index = min(range(len(open_set)), key=lambda index: open_set[index]["f"])
        current = open_set.pop(current_index)
        current_point = current["point"]

        if current_point == goal:
            path = []
            cursor = current
            while cursor:
                path.append(cursor["point"])
                cursor = cursor["parent"]
            return list(reversed(path))

        closed.add(current_point)

        for neighbor in map_neighbors(current_point, cols, rows):
            x, y = neighbor
            if neighbor in closed or grid[x][y] == 1:
                continue

            tentative_g = current["g"] + 1
            existing = next((item for item in open_set if item["point"] == neighbor), None)
            if existing and tentative_g >= existing["g"]:
                continue

            heuristic = abs(goal[0] - x) + abs(goal[1] - y)
            next_node = {
                "point": neighbor,
                "g": tentative_g,
                "h": heuristic,
                "f": tentative_g + heuristic,
                "parent": current,
            }

            if existing:
                open_set.remove(existing)
            open_set.append(next_node)

    return []


def serialize_path_cells(path_cells):
    return [{"x": point[0], "y": point[1]} for point in path_cells]


def step_count_for_path(path_cells):
    return max(len(path_cells) - 1, 0)


def build_unroutable_entries(room_number, deliveries, reason):
    return [
        {
            "room": room_number,
            "reason": reason,
            "med_id": delivery["med_id"],
            "medicine": delivery["medicine"],
            "dosage": delivery["dosage"],
            "patient": delivery["patient"],
            "scheduled_time": delivery["scheduled_time"],
        }
        for delivery in deliveries
    ]


def plan_nearest_neighbor_route(map_payload, grouped_rooms):
    grid = map_payload.get("grid") or []
    base_payload = map_payload.get("base") or DEFAULT_MAP_PAYLOAD["base"]
    room_coordinates = map_payload.get("rooms") or {}

    base_point = (
        int(base_payload.get("x", DEFAULT_MAP_PAYLOAD["base"]["x"])),
        int(base_payload.get("y", DEFAULT_MAP_PAYLOAD["base"]["y"])),
    )

    planned_stops = []
    unroutable_tasks = []
    candidate_rooms = []

    for room_number, room_entry in grouped_rooms.items():
        coordinates = room_coordinates.get(room_number)
        if not coordinates:
            unroutable_tasks.extend(
                build_unroutable_entries(room_number, room_entry["patient_deliveries"], "Room is not mapped.")
            )
            continue

        target_point = (int(coordinates["x"]), int(coordinates["y"]))
        path_from_base = find_map_path(grid, base_point, target_point)
        if not path_from_base:
            unroutable_tasks.extend(
                build_unroutable_entries(
                    room_number,
                    room_entry["patient_deliveries"],
                    "No valid path from base to this room.",
                )
            )
            continue

        candidate_rooms.append(
            {
                "room": room_number,
                "coordinates": {"x": target_point[0], "y": target_point[1]},
                "target_point": target_point,
                "patient_deliveries": room_entry["patient_deliveries"],
            }
        )

    current_point = base_point
    current_room = "BASE"
    total_steps = 0

    while candidate_rooms:
        best_index = None
        best_path = None
        best_steps = None

        for index, room_entry in enumerate(candidate_rooms):
            candidate_path = find_map_path(grid, current_point, room_entry["target_point"])
            if not candidate_path:
                continue

            candidate_steps = step_count_for_path(candidate_path)
            if best_steps is None or candidate_steps < best_steps:
                best_index = index
                best_path = candidate_path
                best_steps = candidate_steps

        if best_index is None:
            for room_entry in candidate_rooms:
                unroutable_tasks.extend(
                    build_unroutable_entries(
                        room_entry["room"],
                        room_entry["patient_deliveries"],
                        f"No valid path from {current_room} to this room.",
                    )
                )
            break

        selected_room = candidate_rooms.pop(best_index)
        planned_stops.append(
            {
                "room": selected_room["room"],
                "coordinates": selected_room["coordinates"],
                "from_room": current_room,
                "patient_deliveries": selected_room["patient_deliveries"],
                "path_cells": serialize_path_cells(best_path),
                "step_count": best_steps,
                "travel_seconds": best_steps * GRID_STEP_SECONDS,
            }
        )
        total_steps += best_steps
        current_point = selected_room["target_point"]
        current_room = selected_room["room"]

    return_path = []
    return_steps = 0
    return_seconds = 0
    return_warning = None
    if planned_stops:
        path_back = find_map_path(grid, current_point, base_point)
        if path_back:
            return_steps = step_count_for_path(path_back)
            return_seconds = return_steps * GRID_STEP_SECONDS
            return_path = serialize_path_cells(path_back)
            total_steps += return_steps
        else:
            return_warning = "No valid return path from the final room to base."

    return {
        "start": {"room": "BASE", "x": base_point[0], "y": base_point[1]},
        "stops": planned_stops,
        "return_path": {
            "to_room": "BASE",
            "path_cells": return_path,
            "step_count": return_steps,
            "travel_seconds": return_seconds,
        },
        "unroutable_tasks": unroutable_tasks,
        "return_warning": return_warning,
        "total_steps": total_steps,
        "total_travel_seconds": total_steps * GRID_STEP_SECONDS,
    }


def build_due_delivery_batch(user):
    due_tasks = collect_due_medication_tasks(user)
    grouped_rooms = group_tasks_by_room(due_tasks)
    map_payload = parse_map_payload(UserMap.query.filter_by(user_id=user.id).first())
    route_plan = plan_nearest_neighbor_route(map_payload, grouped_rooms)

    med_ids = [str(task["med_id"]) for task in due_tasks]
    batch_suffix = "-".join(med_ids) if med_ids else "none"
    route_plan.update(
        {
            "success": True,
            "source_type": "scheduled_medication_batch",
            "batch_id": f"{user.id}-{datetime.now().strftime('%Y%m%d')}-{batch_suffix}",
            "due_task_count": len(due_tasks),
        }
    )
    return route_plan


def create_patient_account(patient, username, password):
    normalized_username = (username or "").strip()
    account = patient_account_for_patient(patient)
    if account:
        normalized_username = normalized_username or account.username
        if not normalized_username:
            return None, "Patient username is required."
        existing = Account.query.filter(Account.username == normalized_username, Account.patient_id != patient.id).first()
        if existing:
            return None, "That patient username is already in use."
        account.username = normalized_username
        if password:
            account.password = generate_password_hash(password, method="pbkdf2:sha256")
    else:
        if not normalized_username or not password:
            return None, "Patient username and password are required."
        existing = Account.query.filter(Account.username == normalized_username, Account.patient_id != patient.id).first()
        if existing:
            return None, "That patient username is already in use."
        account = Account(
            role="PATIENT",
            username=normalized_username,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
            patient_id=patient.id,
            user_id=patient.user_id,
        )
        db.session.add(account)
    return account, "Patient login saved."


def admin_dashboard_redirect(account):
    if account.role == "PATIENT":
        return url_for("patient_dashboard")
    if account.admin_user and not account.admin_user.patients:
        return url_for("setup")
    return url_for("index")


def generate_dummy_video_stream():
    while True:
        yield (
            b"--frame\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"Camera unavailable\r\n"
        )


with app.app_context():
    ensure_legacy_schema()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        account = Account.query.filter_by(role="ADMIN", email=email).first()

        if not account:
            flash("Account not found.", "error")
            return redirect(url_for("register"))
        if not check_password_hash(account.password, password):
            flash("Incorrect password.", "error")
            return redirect(url_for("login"))

        login_user(account)
        return redirect(admin_dashboard_redirect(account))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email:
            flash("Email is required.", "error")
            return redirect(url_for("register"))
        if Account.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for("register"))

        new_user = User(
            username=email,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
        )
        db.session.add(new_user)
        db.session.flush()
        new_account = Account(
            role="ADMIN",
            email=email,
            password=new_user.password,
            user_id=new_user.id,
        )
        db.session.add(new_account)
        db.session.commit()
        login_user(new_account)
        return redirect(url_for("setup"))

    return render_template("register.html")


@app.route("/patient/login", methods=["GET", "POST"])
def patient_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        account = Account.query.filter_by(role="PATIENT", username=username).first()

        if not account:
            flash("Patient account not found.", "error")
            return redirect(url_for("patient_login"))
        if not check_password_hash(account.password, password):
            flash("Incorrect password.", "error")
            return redirect(url_for("patient_login"))

        login_user(account)
        return redirect(url_for("patient_dashboard"))

    return render_template("patient_login.html")


@app.route("/logout")
@login_required
def logout():
    destination = "patient_login" if current_account() and current_account().role == "PATIENT" else "login"
    logout_user()
    return redirect(url_for(destination))


@app.route("/setup", methods=["GET", "POST"])
@admin_required
def setup():
    admin_user = current_admin_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        patients_payload = data.get("patients", [])

        if not patients_payload:
            return jsonify({"success": False, "message": "Add at least one patient."}), 400

        existing_patients = Patient.query.filter_by(user_id=admin_user.id).all()
        for patient in existing_patients:
            RobotTask.query.filter_by(patient_id=patient.id).delete()
            PatientHistory.query.filter_by(patient_id=patient.id).delete()
            account = patient_account_for_patient(patient)
            if account:
                db.session.delete(account)
            Medication.query.filter_by(patient_id=patient.id).delete()
            db.session.delete(patient)
        db.session.flush()

        created_patients = []
        for patient_data in patients_payload:
            patient_name = (patient_data.get("name") or "").strip()
            room_number = normalize_room_number(patient_data.get("room_number"))
            meds_payload = patient_data.get("meds", [])

            if not patient_name:
                return jsonify({"success": False, "message": "Patient name is required."}), 400
            if not validate_room_number(room_number):
                return jsonify(
                    {
                        "success": False,
                        "message": f"Room '{room_number or 'blank'}' is invalid. Use values like A-101.",
                    }
                ), 400
            if not meds_payload:
                return jsonify(
                    {"success": False, "message": f"Add at least one medication for {patient_name}."}
                ), 400

            patient = Patient(name=patient_name, user_id=admin_user.id, room_number=room_number)
            db.session.add(patient)
            db.session.flush()
            created_patients.append(patient)

            for med_data in meds_payload:
                med_name = (med_data.get("name") or "").strip()
                schedule_time = (med_data.get("time") or "").strip()
                dosage = (med_data.get("dosage") or "").strip() or "1 pill"
                instructions = (med_data.get("instructions") or "").strip() or "Manual Add"
                frequency = (med_data.get("frequency") or "Daily").strip()
                selected_days = (med_data.get("selected_days") or "All").strip()
                try:
                    stock_value = int(med_data.get("stock") or 30)
                except (TypeError, ValueError):
                    stock_value = 30

                if not med_name or not schedule_time:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Every medication for {patient_name} needs a name and time.",
                        }
                    ), 400

                db.session.add(
                    Medication(
                        patient_id=patient.id,
                        name=med_name,
                        dosage=dosage,
                        stock=stock_value,
                        max_stock=stock_value,
                        schedule_time=schedule_time,
                        instructions=instructions,
                        frequency=frequency,
                        days=selected_days,
                    )
                )

        for patient in created_patients:
            get_or_create_robot_state(patient.user_id)

        db.session.commit()
        return jsonify({"success": True, "redirect": url_for("index")})

    return render_template("setup.html")


@app.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(admin_dashboard_redirect(current_account()))
    return render_template("landing.html")


@app.route("/dashboard")
@admin_required
def index():
    return render_template("index.html", user=current_admin_user())


@app.route("/patients")
@admin_required
def patients_page():
    admin_user = current_admin_user()
    patients = Patient.query.filter_by(user_id=admin_user.id).order_by(Patient.name.asc()).all()
    recent_history = {patient.id: patient_history_entries(patient, limit=5) for patient in patients}
    return render_template("patients.html", user=admin_user, patients=patients, recent_history=recent_history)


@app.route("/patients/create", methods=["POST"])
@admin_required
def create_patient():
    admin_user = current_admin_user()
    name = (request.form.get("name") or "").strip()
    room_number = normalize_room_number(request.form.get("room_number"))
    if not name or not validate_room_number(room_number):
        flash("Patient name and a valid room number are required.", "error")
        return redirect(url_for("patients_page"))

    patient = Patient(
        user_id=admin_user.id,
        name=name,
        age=int(request.form.get("age")) if (request.form.get("age") or "").isdigit() else None,
        gender=(request.form.get("gender") or "").strip() or None,
        room_number=room_number,
        emergency_notes=(request.form.get("emergency_notes") or "").strip() or None,
    )
    db.session.add(patient)
    db.session.flush()

    username = (request.form.get("patient_username") or "").strip()
    password = request.form.get("patient_password") or ""
    if username or password:
        account, message = create_patient_account(patient, username, password)
        if not account:
            db.session.rollback()
            flash(message, "error")
            return redirect(url_for("patients_page"))

    create_activity(admin_user.id, "Created Patient", f"{patient.name} added in room {patient.room_number}.")
    db.session.commit()
    flash(f"{patient.name} created.", "success")
    return redirect(url_for("patients_page"))


@app.route("/patients/<int:patient_id>/update", methods=["POST"])
@admin_required
def update_patient(patient_id):
    admin_user = current_admin_user()
    patient = get_owned_patient(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_page"))

    name = (request.form.get("name") or "").strip()
    room_number = normalize_room_number(request.form.get("room_number"))
    if not name or not validate_room_number(room_number):
        flash("Patient name and a valid room number are required.", "error")
        return redirect(url_for("patients_page"))

    patient.name = name
    patient.room_number = room_number
    patient.age = int(request.form.get("age")) if (request.form.get("age") or "").isdigit() else None
    patient.gender = (request.form.get("gender") or "").strip() or None
    patient.emergency_notes = (request.form.get("emergency_notes") or "").strip() or None

    username = (request.form.get("patient_username") or "").strip()
    password = request.form.get("patient_password") or ""
    if username or password:
        account, message = create_patient_account(patient, username, password)
        if not account:
            db.session.rollback()
            flash(message, "error")
            return redirect(url_for("patients_page"))

    create_activity(admin_user.id, "Updated Patient", f"{patient.name} profile updated.")
    db.session.commit()
    flash(f"{patient.name} updated.", "success")
    return redirect(url_for("patients_page"))


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
@admin_required
def delete_patient_profile(patient_id):
    admin_user = current_admin_user()
    patient = get_owned_patient(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_page"))

    patient_name = patient.name
    account = patient_account_for_patient(patient)
    RobotTask.query.filter_by(patient_id=patient.id).delete()
    PatientHistory.query.filter_by(patient_id=patient.id).delete()
    Medication.query.filter_by(patient_id=patient.id).delete()
    if account:
        db.session.delete(account)
    db.session.delete(patient)
    create_activity(admin_user.id, "Deleted Patient", f"{patient_name} removed from the portal.")
    db.session.commit()
    flash(f"{patient_name} deleted.", "success")
    return redirect(url_for("patients_page"))


@app.route("/patients/<int:patient_id>/history-note", methods=["POST"])
@admin_required
def add_patient_history_note(patient_id):
    patient = get_owned_patient(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_page"))

    symptom_name = (request.form.get("symptom_name") or "").strip() or None
    details = (request.form.get("details") or "").strip() or None
    improvement_percent = request.form.get("improvement_percent")
    pain_level = request.form.get("pain_level")
    temperature = request.form.get("temperature")
    create_patient_history(
        patient,
        entry_type="progress_update",
        title=(request.form.get("title") or "Caretaker update").strip() or "Caretaker update",
        details=details,
        symptom_name=symptom_name,
        improvement_percent=int(improvement_percent) if (improvement_percent or "").isdigit() else None,
        pain_level=int(pain_level) if (pain_level or "").isdigit() else None,
        temperature=float(temperature) if temperature else None,
        created_by_account=current_account(),
    )
    create_activity(current_admin_user().id, "Caretaker Note Added", f"Progress note added for {patient.name}.")
    db.session.commit()
    flash(f"History updated for {patient.name}.", "success")
    return redirect(url_for("patients_page"))


@app.route("/logs")
@admin_required
def logs_page():
    return render_template("logs.html")


@app.route("/map")
@admin_required
def map_page():
    return render_template("map.html")


@app.route("/history")
@admin_required
def history_page():
    admin_user = current_admin_user()
    logs = (
        ActivityLog.query.filter_by(user_id=admin_user.id)
        .order_by(ActivityLog.timestamp.desc())
        .all()
    )
    stats = stats_payload_for_user(admin_user)
    return render_template("history.html", logs=logs, stats=stats)


@app.route("/patient/dashboard")
@patient_required
def patient_dashboard():
    patient = current_patient_profile()
    return render_template(
        "patient_dashboard.html",
        patient=patient,
        recent_requests=serialize_recent_patient_requests(patient, limit=8),
        history_preview=patient_history_entries(patient, limit=6),
    )


@app.route("/patient/history")
@patient_required
def patient_history_page():
    patient = current_patient_profile()
    return render_template(
        "patient_history.html",
        patient=patient,
        entries=patient_history_entries(patient),
        stats=stats_payload_for_patient(patient),
    )


@app.route("/api/stats")
@admin_required
def get_stats():
    return jsonify(stats_payload_for_user(current_admin_user()))


@app.route("/api/map/save", methods=["POST"])
@admin_required
def save_map():
    admin_user = current_admin_user()
    data = request.get_json(silent=True) or {}
    grid = data.get("grid")
    rooms = data.get("rooms", {})
    base = data.get("base", DEFAULT_MAP_PAYLOAD["base"])

    if not isinstance(grid, list):
        return jsonify({"success": False, "message": "Grid payload is invalid."}), 400
    if not isinstance(rooms, dict):
        rooms = {}
    if not isinstance(base, dict):
        base = DEFAULT_MAP_PAYLOAD["base"].copy()

    normalized_rooms = {}
    for room_name, coords in rooms.items():
        normalized_name = normalize_room_number(room_name)
        if not validate_room_number(normalized_name):
            continue
        if not isinstance(coords, dict):
            continue
        try:
            normalized_rooms[normalized_name] = {
                "x": int(coords.get("x")),
                "y": int(coords.get("y")),
            }
        except (TypeError, ValueError):
            continue

    payload = {"grid": grid, "rooms": normalized_rooms, "base": base}
    save_map_payload(admin_user.id, payload)
    db.session.commit()
    return jsonify({"success": True, "message": "Map layout saved.", **payload})


@app.route("/api/map/load")
@admin_required
def load_map():
    payload = parse_map_payload(UserMap.query.filter_by(user_id=current_admin_user().id).first())
    return jsonify({"success": True, **payload})


@app.route("/api/robot/map/<int:user_id>")
def robot_map(user_id):
    payload = parse_map_payload(UserMap.query.filter_by(user_id=user_id).first())
    return jsonify({"success": True, **payload})


@app.route("/api/schedule")
@admin_required
def get_schedule():
    return jsonify(schedule_payload_for_user(current_admin_user()))


@app.route("/api/schedule/today")
@admin_required
def get_today_schedule():
    return jsonify(today_schedule_api_payload(current_admin_user()))


@app.route("/api/schedule/complete", methods=["POST"])
@admin_required
def complete_schedule_item():
    data = request.get_json(silent=True) or {}
    admin_user = current_admin_user()
    medication = get_owned_medication(data.get("task_id"))
    if not medication:
        return jsonify({"success": False, "message": "Medication not found."}), 404

    today_str = datetime.now().strftime("%Y-%m-%d")
    if medication.last_taken != today_str:
        medication.last_taken = today_str
        if medication.stock > 0:
            medication.stock -= 1
        create_activity(
            admin_user.id,
            f"Dispensed {medication.name}",
            f"Marked complete through dashboard API. Stock now {medication.stock}.",
        )
        create_patient_history(
            medication.patient,
            "medicine_taken",
            title=f"{medication.name} taken",
            details=f"Marked complete by caretaker. Stock now {medication.stock}.",
            medication=medication,
            created_by_account=current_account(),
        )
        db.session.commit()

    return jsonify({"success": True})


@app.route("/api/inventory")
@admin_required
def get_inventory():
    inventory = []
    for patient in current_admin_user().patients:
        for med in patient.medications:
            status = "ok"
            if med.stock < 2:
                status = "low"
            elif med.stock < 5:
                status = "low"

            total = med.max_stock if med.max_stock and med.max_stock > 0 else 30
            inventory.append(
                {
                    "name": f"{med.name} ({patient.name})",
                    "dosage": med.dosage,
                    "stock": med.stock,
                    "total": total,
                    "unit": "tablets",
                    "status": status,
                    "instructions": med.instructions,
                }
            )
    return jsonify(inventory)


@app.route("/api/vitals/current")
@admin_required
def current_vitals():
    state = get_or_create_robot_state(current_admin_user().id)
    return jsonify(
        {
            "heart_rate": state.heart_rate,
            "spo2": state.spo2,
            "temperature": state.temperature,
            "timestamp": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
            "alert": state.heart_rate > 120 or state.heart_rate < 50 or state.spo2 < 92,
        }
    )


@app.route("/api/system/health")
@admin_required
def system_health():
    admin_user = current_admin_user()
    state = get_or_create_robot_state(admin_user.id)
    return jsonify(
        {
            "server": "online",
            "camera": bool(state.camera_available),
            "bluetooth": bool(state.bluetooth_connected),
            "database": True,
            "timestamp": datetime.now().isoformat(),
            "queue_depth": RobotTask.query.filter_by(user_id=admin_user.id, status="queued").count(),
        }
    )


@app.route("/api/robot/status")
@admin_required
def get_robot_status():
    state = get_or_create_robot_state(current_admin_user().id)
    return jsonify(serialize_robot_state(state))


@app.route("/api/robot/get_state")
@admin_required
def get_robot_state():
    state = get_or_create_robot_state(current_admin_user().id)
    return jsonify(serialize_robot_state(state))


@app.route("/api/robot/command", methods=["POST"])
@admin_required
def robot_command():
    admin_user = current_admin_user()
    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip().lower()
    if command not in ROBOT_COMMANDS:
        return jsonify({"success": False, "message": "Unsupported robot command."}), 400

    task, message = queue_robot_command_for_user(admin_user.id, command, source="dashboard")
    create_activity(admin_user.id, "Queued Robot Command", message)
    db.session.commit()
    return jsonify({"success": True, "message": message, "task_id": task.id})


@app.route("/camera/privacy", methods=["POST"])
@admin_required
def toggle_camera_privacy():
    state = get_or_create_robot_state(current_admin_user().id)
    if camera_service and hasattr(camera_service, "toggle_privacy"):
        privacy_mode = camera_service.toggle_privacy()
    else:
        privacy_mode = not state.privacy_mode
    state.privacy_mode = privacy_mode
    state.updated_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True, "privacy_mode": privacy_mode})


@app.route("/video_feed")
@admin_required
def video_feed():
    if camera_service and hasattr(camera_service, "generate_stream"):
        generator = camera_service.generate_stream()
    else:  # pragma: no cover - webcam fallback
        generator = generate_dummy_video_stream()

    return Response(
        stream_with_context(generator),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/ai/symptom-check", methods=["POST"])
@admin_required
def symptom_check():
    admin_user = current_admin_user()
    user_input = (request.get_json(silent=True) or {}).get("symptoms", "")
    if not user_input:
        return jsonify({"success": False, "message": "Please describe the symptoms."}), 400

    if contains_emergency(user_input):
        emergency_msg = (
            "This sounds like a medical emergency. Please stop this chat and call emergency services (911) immediately."
        )
        send_emergency_email(admin_user.username, f"Emergency symptoms reported: {user_input}", recipient_email=get_alert_email_for_user(admin_user))
        create_activity(
            admin_user.id,
            "Symptom Check Emergency",
            f"Emergency symptoms reported: {user_input[:100]}",
        )
        db.session.commit()
        return jsonify({"success": True, "is_emergency": True, "response": emergency_msg})

    if not AI_AVAILABLE:
        return jsonify({"success": False, "message": "AI service currently unavailable."})

    system_instruction = f"""
    You are an expert Medical Triage Assistant.
    CURRENT PATIENT MEDS: {get_user_context(user=admin_user)}

    INSTRUCTIONS:
    1. Start with a brief disclaimer: "I am an AI, not a doctor."
    2. Analyze the user's symptoms: "{user_input}"
    3. Look for potential interactions with their current medications listed above.
    4. Provide 2-3 possible causes, phrased strictly as possibilities.
    5. Suggest the type of doctor they should see.
    6. If the symptoms are vague, ask 2 follow-up questions.
    7. Be empathetic but professional.
    """

    try:
        response = model.generate_content(system_instruction)
        create_activity(
            admin_user.id,
            "Symptom Check",
            f"User queried: {user_input[:80]}",
        )
        db.session.commit()
        return jsonify({"success": True, "is_emergency": False, "response": response.text})
    except Exception as ai_error:
        print(f"AI error: {ai_error}")
        return jsonify({"success": False, "error": "The AI agent is resting. Please try again later."})


@app.route("/api/voice/process", methods=["POST"])
@admin_required
def process_voice():
    user_text = (request.get_json(silent=True) or {}).get("text", "")
    result = interpret_command_text(
        current_admin_user(),
        user_text,
        source="voice",
        created_by_account=current_account(),
    )
    if result["success"]:
        db.session.commit()
        return jsonify(result)
    db.session.rollback()
    return jsonify(result), 400


@app.route("/api/task/add", methods=["POST"])
@admin_required
def add_task():
    admin_user = current_admin_user()
    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id")
    patient = get_owned_patient(patient_id) if patient_id else get_primary_patient(admin_user)
    if not patient:
        return jsonify({"success": False, "message": "Select a valid patient first."}), 400

    name = (data.get("name") or "").strip()
    schedule_time = (data.get("time") or "").strip()
    if not name or not schedule_time:
        return jsonify({"success": False, "message": "Medicine name and time are required."}), 400

    dosage = (data.get("dosage") or "").strip() or "1 pill"
    instructions = (data.get("instructions") or "").strip() or "Manual Add"
    try:
        stock_value = int(data.get("stock") or 30)
    except (TypeError, ValueError):
        stock_value = 30

    new_med = Medication(
        patient_id=patient.id,
        name=name,
        dosage=dosage,
        stock=stock_value,
        max_stock=stock_value,
        schedule_time=schedule_time,
        instructions=instructions,
        frequency="Daily",
        days="All",
    )
    db.session.add(new_med)
    create_activity(
        admin_user.id,
        f"Added {name}",
        f"Medication added for {patient.name} at {schedule_time} in room {patient.room_number}.",
    )
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/task/delete", methods=["POST"])
@admin_required
def delete_task():
    admin_user = current_admin_user()
    medication = get_owned_medication((request.get_json(silent=True) or {}).get("id"))
    if not medication:
        return jsonify({"success": False, "message": "Medication not found."}), 404

    med_name = medication.name
    db.session.delete(medication)
    create_activity(admin_user.id, f"Deleted {med_name}", "Medication removed from schedule.")
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/task/toggle", methods=["POST"])
@admin_required
def toggle_task():
    admin_user = current_admin_user()
    medication = get_owned_medication((request.get_json(silent=True) or {}).get("id"))
    if not medication:
        return jsonify({"success": False, "message": "Medication not found."}), 404

    today_str = datetime.now().strftime("%Y-%m-%d")

    if medication.last_taken == today_str:
        medication.last_taken = None
        if medication.stock < medication.max_stock:
            medication.stock += 1
        create_activity(
            admin_user.id,
            f"Undo: {medication.name}",
            f"Stock restored to {medication.stock}.",
        )
    else:
        if medication.stock <= 0:
            return jsonify({"success": False, "message": "Out of stock."}), 400
        medication.last_taken = today_str
        medication.stock -= 1
        create_activity(
            admin_user.id,
            f"Dispensed {medication.name}",
            f"Stock reduced to {medication.stock}.",
        )
        create_patient_history(
            medication.patient,
            "medicine_taken",
            title=f"{medication.name} taken",
            details=f"Marked complete by caretaker. Stock reduced to {medication.stock}.",
            medication=medication,
            created_by_account=current_account(),
        )

    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/request", methods=["POST"])
@admin_required
def handle_request():
    admin_user = current_admin_user()
    data = request.get_json(silent=True) or {}
    request_type = (data.get("type") or "").strip().lower()
    if request_type not in {"medicine", "water", "help"}:
        return jsonify({"success": False, "message": "Unsupported request type."}), 400

    task, message = create_dashboard_request(
        admin_user,
        request_type,
        source="dashboard",
        created_by_account=current_account(),
    )
    if not task:
        db.session.rollback()
        return jsonify({"success": False, "message": message}), 400

    db.session.commit()
    return jsonify({"success": True, "message": message, "task_id": task.id, "status": task.status})


@app.route("/api/emergency", methods=["POST"])
@admin_required
def emergency_request():
    admin_user = current_admin_user()
    task, message = create_dashboard_request(
        admin_user,
        "help",
        source="dashboard",
        created_by_account=current_account(),
    )
    if not task:
        db.session.rollback()
        return jsonify({"success": False, "message": message}), 400

    queue_robot_command_for_user(admin_user.id, "emergency", source="dashboard")
    db.session.commit()
    return jsonify({"success": True, "message": message})


@app.route("/api/patients/<int:patient_id>/history")
@admin_required
def admin_patient_history_api(patient_id):
    patient = get_owned_patient(patient_id)
    if not patient:
        return jsonify({"success": False, "message": "Patient not found."}), 404
    return jsonify({"success": True, "entries": [serialize_patient_history(entry) for entry in patient_history_entries(patient)]})


@app.route("/patient/api/request", methods=["POST"])
@patient_required
def patient_request():
    patient = current_patient_profile()
    data = request.get_json(silent=True) or {}
    request_type = (data.get("type") or "").strip().lower()
    if request_type not in {"medicine", "water", "help"}:
        return jsonify({"success": False, "message": "Unsupported request type."}), 400

    task, message = create_request_for_patient(
        patient,
        request_type,
        source="patient_portal",
        created_by_account=current_account(),
    )
    if not task:
        db.session.rollback()
        return jsonify({"success": False, "message": message}), 400

    db.session.commit()
    return jsonify({"success": True, "message": message, "task_id": task.id, "status": task.status})


@app.route("/patient/api/requests")
@patient_required
def patient_requests_api():
    return jsonify({"success": True, "items": serialize_recent_patient_requests(current_patient_profile(), limit=12)})


@app.route("/patient/api/history")
@patient_required
def patient_history_api():
    patient = current_patient_profile()
    return jsonify({"success": True, "entries": [serialize_patient_history(entry) for entry in patient_history_entries(patient)]})


@app.route("/patient/api/voice/process", methods=["POST"])
@patient_required
def patient_voice_process():
    patient = current_patient_profile()
    user_text = (request.get_json(silent=True) or {}).get("text", "")
    result = interpret_patient_command_text(
        patient,
        user_text,
        source="patient_voice",
        created_by_account=current_account(),
    )
    if result["success"]:
        db.session.commit()
        return jsonify(result)
    db.session.rollback()
    return jsonify(result), 400


@app.route("/patient/api/ai/symptom-check", methods=["POST"])
@patient_required
def patient_symptom_check():
    patient = current_patient_profile()
    user_input = (request.get_json(silent=True) or {}).get("symptoms", "")
    if not user_input:
        return jsonify({"success": False, "message": "Please describe the symptoms."}), 400

    if contains_emergency(user_input):
        emergency_msg = (
            "This sounds like a medical emergency. Please stop this chat and call emergency services (911) immediately."
        )
        send_emergency_email(
            patient.name,
            f"Emergency symptoms reported by patient: {user_input}",
            recipient_email=get_alert_email_for_user(patient.caregiver),
        )
        create_activity(
            patient.user_id,
            "Patient Symptom Check Emergency",
            f"{patient.name} reported emergency symptoms: {user_input[:100]}",
        )
        db.session.commit()
        return jsonify({"success": True, "is_emergency": True, "response": emergency_msg})

    if not AI_AVAILABLE:
        return jsonify({"success": False, "message": "AI service currently unavailable."})

    system_instruction = f"""
    You are an expert Medical Triage Assistant.
    CURRENT PATIENT MEDS: {get_user_context(patient=patient)}

    INSTRUCTIONS:
    1. Start with a brief disclaimer: "I am an AI, not a doctor."
    2. Analyze the user's symptoms: "{user_input}"
    3. Look for potential interactions with their current medications listed above.
    4. Provide 2-3 possible causes, phrased strictly as possibilities.
    5. Suggest the type of doctor they should see.
    6. If the symptoms are vague, ask 2 follow-up questions.
    7. Be empathetic but professional.
    """

    try:
        response = model.generate_content(system_instruction)
        create_activity(patient.user_id, "Patient Symptom Check", f"{patient.name} queried: {user_input[:80]}")
        db.session.commit()
        return jsonify({"success": True, "is_emergency": False, "response": response.text})
    except Exception as ai_error:
        print(f"AI error: {ai_error}")
        return jsonify({"success": False, "error": "The AI agent is resting. Please try again later."})


@app.route("/api/robot/heartbeat/<int:user_id>", methods=["POST"])
def robot_heartbeat(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    data = request.get_json(silent=True) or {}
    state = get_or_create_robot_state(user_id)
    for field in [
        "battery_level",
        "location",
        "is_moving",
        "wifi_signal",
        "drawer_open",
        "current_task",
        "heart_rate",
        "spo2",
        "temperature",
        "bluetooth_connected",
        "camera_available",
        "privacy_mode",
        "current_stop_index",
        "remaining_stops",
        "estimated_remaining_seconds",
    ]:
        if field in data:
            setattr(state, field, data[field])
    state.last_heartbeat = datetime.now()
    state.updated_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/robot/queue/<int:user_id>")
def robot_queue(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    queued_task = next_queued_robot_task(user_id)
    if queued_task:
        return jsonify({"success": True, "task": queued_task})

    return jsonify({"success": True, "task": None})


@app.route("/api/robot/task/complete", methods=["POST"])
def robot_task_complete():
    data = request.get_json(silent=True) or {}
    task = db.session.get(RobotTask, data.get("task_id"))
    if not task:
        return jsonify({"success": False, "message": "Task not found."}), 404

    task.status = "completed"
    task.completed_at = datetime.now()
    task.updated_at = datetime.now()

    state = get_or_create_robot_state(task.user_id)
    state.current_task = "Idle"
    state.is_moving = False
    state.location = data.get("location", state.location)
    state.current_stop_index = 0
    state.remaining_stops = 0
    state.estimated_remaining_seconds = 0
    if task.task_type == "robot_command":
        try:
            payload = json.loads(task.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        command = payload.get("command")
        if command == "open_drawer":
            state.drawer_open = True
        elif command == "close_drawer":
            state.drawer_open = False

    details = data.get("details") or task.response_message or f"{task.task_type} completed."
    create_activity(task.user_id, "Robot Task Completed", details)
    if task.patient and task.task_type in {"water_delivery", "help_request"}:
        history_type = "water_requested" if task.task_type == "water_delivery" else "sos_alert"
        create_patient_history(
            task.patient,
            history_type,
            title=task.response_message or task.task_type.replace("_", " ").title(),
            details=details,
            request_task=task,
        )
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/robot/task/fail", methods=["POST"])
def robot_task_fail():
    data = request.get_json(silent=True) or {}
    task = db.session.get(RobotTask, data.get("task_id"))
    if not task:
        return jsonify({"success": False, "message": "Task not found."}), 404

    task.status = "failed"
    task.failed_at = datetime.now()
    task.updated_at = datetime.now()

    state = get_or_create_robot_state(task.user_id)
    state.current_task = "Idle"
    state.is_moving = False
    state.current_stop_index = 0
    state.remaining_stops = 0
    state.estimated_remaining_seconds = 0
    create_activity(
        task.user_id,
        "Robot Task Failed",
        data.get("error") or f"{task.task_type} failed on robot.",
    )
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/robot/check/<int:user_id>")
def robot_check_schedule(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    return jsonify(build_due_delivery_batch(user))


@app.route("/api/robot/mission_log", methods=["POST"])
def robot_mission_log():
    data = request.get_json(silent=True) or {}
    user = db.session.get(User, data.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    action = (data.get("action") or "Robot Mission Update").strip()
    details = (data.get("details") or "Mission progress reported from the robot.").strip()
    create_activity(user.id, action[:100], details[:200])
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/robot/complete", methods=["POST"])
def robot_mark_complete():
    data = request.get_json(silent=True) or {}
    med = db.session.get(Medication, data.get("med_id"))
    if not med:
        return jsonify({"success": False, "message": "Medication not found."}), 400

    today_str = datetime.now().strftime("%Y-%m-%d")
    if med.last_taken != today_str:
        med.last_taken = today_str
        if med.stock > 0:
            med.stock -= 1
        create_activity(
            med.patient.user_id,
            (data.get("action") or f"Robot Dispensed {med.name}")[:100],
            (
                data.get("details")
                or f"Auto-dispensed by Pi for room {med.patient.room_number}. Stock now {med.stock}."
            )[:200],
        )
        create_patient_history(
            med.patient,
            "medicine_taken",
            title=f"{med.name} taken",
            details=(data.get("details") or f"Robot delivery completed for {med.name}.")[:300],
            medication=med,
        )

    state = get_or_create_robot_state(med.patient.user_id)
    if not data.get("mission_active"):
        state.current_task = "Idle"
        state.is_moving = False
        state.current_stop_index = 0
        state.remaining_stops = 0
        state.estimated_remaining_seconds = 0
        if "location" in data:
            state.location = data.get("location")
    db.session.commit()
    return jsonify({"success": True})


@app.route("/seed_full_day")
@admin_required
def seed_full_day():
    admin_user = current_admin_user()
    patient = Patient.query.filter_by(user_id=admin_user.id).first()
    if not patient:
        patient = Patient(name="Grandpa Joe", user_id=admin_user.id, room_number="A-101")
        db.session.add(patient)
        db.session.flush()

    schedule_data = [
        {"name": "Omeprazole", "dosage": "20mg", "time": "08:00", "instructions": "Stomach Protector", "stock": 28, "max": 30},
        {"name": "Metformin", "dosage": "500mg", "time": "08:00", "instructions": "Diabetes", "stock": 60, "max": 60},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "08:00", "instructions": "Antibiotic", "stock": 21, "max": 21},
        {"name": "Aspirin", "dosage": "75mg", "time": "08:00", "instructions": "Heart Health", "stock": 30, "max": 30},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "13:00", "instructions": "Antibiotic Dose 2", "stock": 21, "max": 21},
        {"name": "Vitamin D3", "dosage": "1000 IU", "time": "13:00", "instructions": "Bone Supplement", "stock": 90, "max": 90},
        {"name": "Metformin", "dosage": "500mg", "time": "20:00", "instructions": "Diabetes Evening", "stock": 60, "max": 60},
        {"name": "Amoxicillin", "dosage": "500mg", "time": "20:00", "instructions": "Antibiotic Dose 3", "stock": 21, "max": 21},
        {"name": "Atorvastatin", "dosage": "20mg", "time": "20:00", "instructions": "Cholesterol", "stock": 30, "max": 30},
    ]

    added = 0
    for item in schedule_data:
        exists = Medication.query.filter_by(
            name=item["name"], schedule_time=item["time"], patient_id=patient.id
        ).first()
        if exists:
            continue
        db.session.add(
            Medication(
                patient_id=patient.id,
                name=item["name"],
                dosage=item["dosage"],
                stock=item["stock"],
                max_stock=item["max"],
                schedule_time=item["time"],
                instructions=item["instructions"],
                frequency="Daily",
                days="All",
                last_taken=None,
            )
        )
        added += 1

    db.session.commit()
    return f"""<div style="font-family:sans-serif;text-align:center;padding:50px;background:#111;color:white;">
    <h1 style="color:#48bb78;">System Seeded</h1><p>Added {added} complex medications.</p>
    <a href='/dashboard' style="background:#0a84ff;color:white;padding:15px;text-decoration:none;border-radius:20px;">Back to Dashboard</a></div>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
