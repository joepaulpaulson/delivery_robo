import sys
import os
from datetime import datetime, timedelta

# Import your app and db
sys.path.append(os.path.dirname(__file__))

from app import app, db, User, Patient, Medication
from werkzeug.security import generate_password_hash


def seed():
    with app.app_context():

        print("🧹 Resetting database...")
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

        john_time = now.strftime("%H:%M")  # immediate
        alice_time = (now + timedelta(minutes=3)).strftime("%H:%M")  # +3 min

        print(f"\n⏰ John Time (Immediate): {john_time}")
        print(f"⏰ Alice Time (+3 min): {alice_time}")

        # ================= PATIENTS =================
        p1 = Patient(name="John", user_id=user.id, room_number="A-101")
        p2 = Patient(name="Alice", user_id=user.id, room_number="A-102")

        db.session.add_all([p1, p2])
        db.session.commit()

        # ================= MEDICATIONS =================
        meds = [

            # JOHN → immediate execution
            Medication(
                patient_id=p1.id,
                name="Paracetamol",
                dosage="1 tablet",
                stock=30,
                max_stock=30,
                schedule_time=john_time,
                instructions="Pain relief",
                frequency="Daily",
                days="All",
                last_taken=None
            ),

            # ALICE → after 3 minutes
            Medication(
                patient_id=p2.id,
                name="Metformin",
                dosage="500mg",
                stock=30,
                max_stock=30,
                schedule_time=alice_time,
                instructions="Diabetes",
                frequency="Daily",
                days="All",
                last_taken=None
            )
        ]

        db.session.add_all(meds)
        db.session.commit()

        # ================= OUTPUT =================
        print("\n✅ SEED COMPLETE\n")

        print("👤 LOGIN:")
        print("   Username: admin")
        print("   Password: admin123\n")

        print("👨‍⚕️ PATIENTS:")
        print("   - John → Room A-101")
        print("   - Alice → Room A-102\n")

        print("🤖 EXECUTION FLOW:")
        print("   1. Robot serves John immediately")
        print("   2. Robot returns to base")
        print("   3. Waits 3 minutes")
        print("   4. Robot serves Alice")
        print("   5. Robot returns to base\n")

        print("💡 NOTE:")
        print("   Make sure your Pi is running and polling every 5 seconds.")


if __name__ == "__main__":
    seed()