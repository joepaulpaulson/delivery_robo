from pathlib import Path
import sqlite3

from app import Account, Medication, Patient, User, app, db, ensure_legacy_schema


BASE_DIR = Path(__file__).resolve().parent
CANONICAL_DB = BASE_DIR / "database" / "medical_robot.db"
LEGACY_DB = BASE_DIR / "instance" / "medical_robot.db"


def legacy_tables(connection):
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def fetch_rows(connection, table_name):
    connection.row_factory = sqlite3.Row
    return connection.execute(f"SELECT * FROM {table_name} ORDER BY id").fetchall()


def ensure_admin_account(user, email, password):
    account = Account.query.filter_by(user_id=user.id, role="ADMIN").first()
    if account:
        changed = False
        if account.email != email:
            account.email = email
            changed = True
        if password and account.password != password:
            account.password = password
            changed = True
        return 0, int(changed)

    db.session.add(
        Account(
            role="ADMIN",
            email=email,
            password=password or user.password,
            user_id=user.id,
        )
    )
    db.session.flush()
    return 1, 0


def migrate_legacy_database():
    summary = {
        "users_created": 0,
        "accounts_created": 0,
        "accounts_updated": 0,
        "patients_created": 0,
        "medications_created": 0,
    }

    if not LEGACY_DB.exists() or LEGACY_DB.resolve() == CANONICAL_DB.resolve():
        return summary

    with sqlite3.connect(LEGACY_DB) as connection:
        tables = legacy_tables(connection)
        if "user" not in tables:
            return summary

        user_id_map = {}
        patient_id_map = {}

        for row in fetch_rows(connection, "user"):
            username = (row["username"] or "").strip().lower()
            if not username:
                continue

            user = User.query.filter_by(username=username).first()
            if user is None:
                user = User(username=username, password=row["password"])
                db.session.add(user)
                db.session.flush()
                summary["users_created"] += 1
            elif row["password"] and user.password != row["password"]:
                user.password = row["password"]

            user_id_map[row["id"]] = user.id
            created, updated = ensure_admin_account(user, username, row["password"])
            summary["accounts_created"] += created
            summary["accounts_updated"] += updated

        if "patient" in tables:
            for row in fetch_rows(connection, "patient"):
                mapped_user_id = user_id_map.get(row["user_id"])
                if not mapped_user_id:
                    continue

                patient = Patient.query.filter_by(
                    user_id=mapped_user_id,
                    name=row["name"],
                ).first()
                if patient is None:
                    patient = Patient(
                        user_id=mapped_user_id,
                        name=row["name"],
                        room_number="A-101",
                    )
                    db.session.add(patient)
                    db.session.flush()
                    summary["patients_created"] += 1

                patient_id_map[row["id"]] = patient.id

        if "medication" in tables:
            for row in fetch_rows(connection, "medication"):
                mapped_patient_id = patient_id_map.get(row["patient_id"])
                if not mapped_patient_id:
                    continue

                medication = Medication.query.filter_by(
                    patient_id=mapped_patient_id,
                    name=row["name"],
                    schedule_time=row["schedule_time"],
                ).first()
                if medication is not None:
                    continue

                db.session.add(
                    Medication(
                        patient_id=mapped_patient_id,
                        name=row["name"],
                        dosage=row["dosage"],
                        stock=row["stock"] if row["stock"] is not None else 30,
                        max_stock=row["stock"] if row["stock"] is not None else 30,
                        schedule_time=row["schedule_time"],
                        instructions="Imported from legacy database",
                        frequency="Daily",
                        days="All",
                        last_taken=None,
                    )
                )
                summary["medications_created"] += 1

        db.session.commit()

    return summary


def main():
    with app.app_context():
        ensure_legacy_schema()
        summary = migrate_legacy_database()
        print("Migration complete.")
        print(f"Canonical database: {CANONICAL_DB}")
        print(f"Legacy database: {LEGACY_DB}")
        for key, value in summary.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
