import sqlite3

# Connect to your database
# This path matches your folder structure: database/medical_robot.db
conn = sqlite3.connect('database/medical_robot.db')
cursor = conn.cursor()

try:
    # Fetch all users
    cursor.execute("SELECT id, username FROM user")
    users = cursor.fetchall()

    print("\n--- USER LIST ---")
    print(f"{'ID':<5} | {'USERNAME'}")
    print("-" * 20)

    for user in users:
        print(f"{user[0]:<5} | {user[1]}")

    print("-" * 20)

except Exception as e:
    print(f"Error reading database: {e}")

finally:
    conn.close()