import sys
import os

# Make sure we can import app
sys.path.append(os.path.dirname(__file__))

from app import app, db

def reset_database():
    with app.app_context():
        print("⚠️ Resetting database...")

        db.drop_all()
        db.create_all()

        print("✅ Database reset complete.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to DELETE all data? (y/n): ")

    if confirm.lower() == 'y':
        reset_database()
    else:
        print("❌ Reset cancelled.")