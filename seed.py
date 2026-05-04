import sys
import os
from datetime import datetime, timedelta

# Import your app and db
sys.path.append(os.path.dirname(__file__))

from app import app, db, User, Patient, Medication
from werkzeug.security import generate_password_hash

def seed():
    with app.app_context():

        print("🧹 Clearing old data...")
        db.drop_all()
        db.create_all()

        # ================= USER =================
        user = User(
            username="admin",
            password=generate_password_hash("admin123")
        )
        db.session.add(user)
        db.session.commit()

        # ================= TIME SETUP =================
        now = datetime.now()

        past_time = (now - timedelta(minutes=5)).strftime("%H:%M")
        current_time = now.strftime("%H:%M")
        future_time = (now + timedelta(minutes=5)).strftime("%H:%M")

        print(f"⏰ Past: {past_time}")
        print(f"⏰ Now: {current_time}")
        print(f"⏰ Future: {future_time}")

        # ================= PATIENTS =================
        p1 = Patient(name="John", user_id=user.id, room_number="A-101")
        p2 = Patient(name="Alice", user_id=user.id, room_number="A-102")

        db.session.add_all([p1, p2])
        db.session.commit()

        # ================= MEDICATIONS =================
        meds = [
            # PAST (should trigger immediately)
            Medication(
                patient_id=p1.id,
                name="Paracetamol",
                dosage="1 tablet",
                stock=30,
                max_stock=30,
                schedule_time=past_time,
                instructions="Pain relief",
                frequency="Daily",
                days="All"
            ),

            # CURRENT
            Medication(
                patient_id=p1.id,
                name="Aspirin",
                dosage="75mg",
                stock=30,
                max_stock=30,
                schedule_time=current_time,
                instructions="Heart",
                frequency="Daily",
                days="All"
            ),

            # FUTURE (+5 min)
            Medication(
                patient_id=p2.id,
                name="Metformin",
                dosage="500mg",
                stock=30,
                max_stock=30,
                schedule_time=future_time,
                instructions="Diabetes",
                frequency="Daily",
                days="All"
            )
        ]

        db.session.add_all(meds)
        db.session.commit()

        print("\n✅ SEED COMPLETE")
        print("👤 User: admin / admin123")
        print("👨‍⚕️ Patients:")
        print("   - John (A-101)")
        print("   - Alice (A-102)")
        print("💊 Meds:")
        print("   - Past → triggers immediately")
        print("   - Now → triggers now")
        print("   - Future → triggers in 5 mins")

if __name__ == "__main__":
    seed()