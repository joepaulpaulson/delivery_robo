import os
import sys
import time

import requests
import serial
from gtts import gTTS

from navigation import (
    deserialize_path_cells,
    execute_path_cells,
    navigate_to_room,
    return_to_base,
)


SERVER_URL = "http://192.168.18.62:5000"
USER_ID = 1
PORT_NAME = "/dev/ttyUSB0"
POLL_INTERVAL_SECONDS = 3


try:
    arduino = serial.Serial(PORT_NAME, 9600, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()
    print(f"Real hardware connected: {PORT_NAME}")
except Exception:
    print(f"Fatal error: Arduino not found at {PORT_NAME}")
    sys.exit(1)


def speak(text):
    print(f"Speaking: {text}")
    try:
        tts = gTTS(text=text, lang="en")
        tts.save("robot_voice.mp3")
        os.system("mpg321 robot_voice.mp3 --quiet")
    except Exception as error:
        print(f"Audio error: {error}")


def send_command(command, duration):
    print(f"Sending '{command}' for {duration} second(s)...")
    arduino.write(command.encode())
    time.sleep(duration)
    arduino.write(b"S")
    time.sleep(0.5)


def post_heartbeat(**payload):
    try:
        requests.post(
            f"{SERVER_URL}/api/robot/heartbeat/{USER_ID}",
            json=payload,
            timeout=10,
        )
    except Exception as error:
        print(f"Heartbeat failed: {error}")


def post_mission_log(action, details):
    try:
        requests.post(
            f"{SERVER_URL}/api/robot/mission_log",
            json={"user_id": USER_ID, "action": action, "details": details},
            timeout=10,
        )
    except Exception as error:
        print(f"Mission log failed: {error}")


def complete_robot_task(task_id, details, location="Dock"):
    try:
        requests.post(
            f"{SERVER_URL}/api/robot/task/complete",
            json={"task_id": task_id, "details": details, "location": location},
            timeout=10,
        )
    except Exception as error:
        print(f"Task completion update failed: {error}")


def fail_robot_task(task_id, error_message):
    try:
        requests.post(
            f"{SERVER_URL}/api/robot/task/fail",
            json={"task_id": task_id, "error": error_message},
            timeout=10,
        )
    except Exception as error:
        print(f"Task failure update failed: {error}")


def complete_medication(med_id, *, mission_active=False, details=None, location=None):
    try:
        payload = {"med_id": med_id}
        if mission_active:
            payload["mission_active"] = True
        if details:
            payload["details"] = details
        if location:
            payload["location"] = location
        requests.post(
            f"{SERVER_URL}/api/robot/complete",
            json=payload,
            timeout=10,
        )
    except Exception as error:
        print(f"Medication completion update failed: {error}")


def execute_robot_command(command):
    print(f"Executing direct robot command: {command}")

    if command == "forward":
        send_command("F", 1)
    elif command == "backward":
        send_command("B", 1)
    elif command == "left":
        send_command("L", 0.8)
    elif command == "right":
        send_command("R", 0.8)
    elif command == "open_drawer":
        arduino.write(b"O")
    elif command == "close_drawer":
        arduino.write(b"C")
    elif command == "emergency":
        arduino.write(b"S")
        speak("Emergency stop activated.")
    else:
        arduino.write(b"S")

    post_heartbeat(
        current_task=f"Executed {command}",
        is_moving=command in {"forward", "backward", "left", "right"},
        drawer_open=command == "open_drawer",
        location="Dock",
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )


def run_delivery_sequence(patient_name, item_name, dosage, room, *, drawer_message, wait_seconds=15):
    print(f"Starting delivery: {item_name} for {patient_name} in room {room}")
    post_heartbeat(
        current_task=f"Delivering {item_name}",
        is_moving=True,
        location=f"En route to {room}",
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )

    speak(f"Delivering {item_name} for {patient_name} to room {room}.")
    path = navigate_to_room(room, send_command, SERVER_URL, USER_ID)

    post_heartbeat(
        current_task=f"At {room}",
        is_moving=False,
        location=room,
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )
    speak(drawer_message)
    arduino.write(b"O")
    post_heartbeat(
        drawer_open=True,
        current_task=f"Serving {item_name}",
        is_moving=False,
        location=room,
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )

    print(f"Waiting {wait_seconds} seconds...")
    time.sleep(wait_seconds)

    arduino.write(b"C")
    post_heartbeat(
        drawer_open=False,
        current_task="Returning to dock",
        is_moving=True,
        location=f"Leaving {room}",
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )
    speak("Task complete. Returning to the dock.")
    return_to_base(path, send_command)
    post_heartbeat(
        current_task="Idle",
        is_moving=False,
        location="Dock",
        drawer_open=False,
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )


def remaining_batch_seconds(batch, next_stop_index):
    remaining = 0
    for stop in (batch.get("stops") or [])[next_stop_index:]:
        remaining += int(stop.get("travel_seconds") or 0)
    remaining += int((batch.get("return_path") or {}).get("travel_seconds") or 0)
    return remaining


def fetch_due_batch():
    response = requests.get(f"{SERVER_URL}/api/robot/check/{USER_ID}", timeout=10)
    response.raise_for_status()
    return response.json()


def execute_scheduled_batch(batch):
    stops = batch.get("stops") or []
    total_stops = len(stops)
    if not total_stops:
        unroutable_tasks = batch.get("unroutable_tasks") or []
        if unroutable_tasks:
            reasons = ", ".join(
                f"{item.get('room')}: {item.get('reason')}" for item in unroutable_tasks[:3]
            )
            print(f"No executable batch route. {reasons}")
            post_heartbeat(
                current_task="Waiting for mapped route",
                is_moving=False,
                location="Dock",
                current_stop_index=0,
                remaining_stops=0,
                estimated_remaining_seconds=0,
            )
        return False

    batch_id = batch.get("batch_id", "batch")
    unroutable_tasks = batch.get("unroutable_tasks") or []
    if unroutable_tasks:
        warning_rooms = ", ".join(sorted({item.get("room") for item in unroutable_tasks if item.get("room")}))
        post_mission_log(
            "Robot Mission Warning",
            f"Batch {batch_id} started with unroutable rooms excluded: {warning_rooms}.",
        )

    print(f"Executing medication batch {batch_id} with {total_stops} stops.")
    post_mission_log(
        "Robot Mission Started",
        f"Batch {batch_id} started with {batch.get('due_task_count', 0)} due deliveries across {total_stops} mapped stops.",
    )
    speak(f"Starting medication round with {total_stops} room stops.")

    heading = "N"
    post_heartbeat(
        current_task=f"Medication batch {batch_id}",
        is_moving=False,
        location="Dock",
        drawer_open=False,
        current_stop_index=0,
        remaining_stops=total_stops,
        estimated_remaining_seconds=int(batch.get("total_travel_seconds") or 0),
    )

    for stop_index, stop in enumerate(stops, start=1):
        room = stop.get("room", "Unknown Room")
        deliveries = stop.get("patient_deliveries") or []
        travel_path = deserialize_path_cells(stop.get("path_cells"))
        eta_seconds = remaining_batch_seconds(batch, stop_index - 1)

        post_heartbeat(
            current_task=f"Medication batch stop {stop_index}/{total_stops}",
            is_moving=True,
            location=f"En route to {room}",
            drawer_open=False,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index + 1,
            estimated_remaining_seconds=eta_seconds,
        )
        speak(f"Heading to room {room}. Stop {stop_index} of {total_stops}.")
        _, heading = execute_path_cells(travel_path, send_command, initial_heading=heading)

        post_heartbeat(
            current_task=f"Serving room {room}",
            is_moving=False,
            location=room,
            drawer_open=False,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_remaining_seconds=remaining_batch_seconds(batch, stop_index),
        )

        patient_names = ", ".join(
            sorted({delivery.get("patient", "the patient") for delivery in deliveries})
        )
        speak(f"Arrived at room {room}. Delivering medication for {patient_names}.")
        arduino.write(b"O")
        post_heartbeat(
            current_task=f"Serving room {room}",
            is_moving=False,
            location=room,
            drawer_open=True,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_remaining_seconds=remaining_batch_seconds(batch, stop_index),
        )
        time.sleep(18)

        for delivery in deliveries:
            details = (
                f"Delivered {delivery.get('medicine', 'medication')} "
                f"({delivery.get('dosage', 'dose')}) to {delivery.get('patient', 'the patient')} "
                f"in room {room} as part of batch {batch_id}."
            )
            complete_medication(
                delivery["med_id"],
                mission_active=True,
                details=details,
                location=room,
            )
            post_mission_log("Robot Delivery Completed", details)

        arduino.write(b"C")
        post_heartbeat(
            current_task=f"Completed room {room}",
            is_moving=False,
            location=room,
            drawer_open=False,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_remaining_seconds=remaining_batch_seconds(batch, stop_index),
        )

    return_path = deserialize_path_cells((batch.get("return_path") or {}).get("path_cells"))
    return_seconds = int((batch.get("return_path") or {}).get("travel_seconds") or 0)
    if return_path:
        post_heartbeat(
            current_task="Returning to dock",
            is_moving=True,
            location="Returning to base",
            drawer_open=False,
            current_stop_index=total_stops,
            remaining_stops=0,
            estimated_remaining_seconds=return_seconds,
        )
        speak("Medication round complete. Returning to the dock.")
        _, heading = execute_path_cells(return_path, send_command, initial_heading=heading)

    post_heartbeat(
        current_task="Idle",
        is_moving=False,
        location="Dock",
        drawer_open=False,
        current_stop_index=0,
        remaining_stops=0,
        estimated_remaining_seconds=0,
    )
    post_mission_log(
        "Robot Mission Completed",
        f"Batch {batch_id} completed after serving {total_stops} stops.",
    )
    return True


def handle_robot_task(task):
    task_id = task["id"]
    task_type = task.get("task_type")
    payload = task.get("payload") or {}

    try:
        if task_type == "robot_command":
            command = payload.get("command", "stop")
            execute_robot_command(command)
            complete_robot_task(task_id, f"Executed robot command: {command}")
            return

        if task_type == "room_navigation":
            room = task.get("room") or payload.get("room_number") or "A-101"
            post_heartbeat(current_task=f"Navigating to {room}", is_moving=True, location=f"En route to {room}")
            path = navigate_to_room(room, send_command, SERVER_URL, USER_ID)
            speak(f"Arrived at room {room}. Returning to dock.")
            return_to_base(path, send_command)
            post_heartbeat(
                current_task="Idle",
                is_moving=False,
                location="Dock",
                current_stop_index=0,
                remaining_stops=0,
                estimated_remaining_seconds=0,
            )
            complete_robot_task(task_id, f"Navigation to {room} completed.")
            return

        patient = task.get("patient") or payload.get("patient_name") or "the patient"
        room = task.get("room") or payload.get("room_number") or "A-101"

        if task_type == "medicine_delivery":
            run_delivery_sequence(
                patient,
                "medication assistance",
                payload.get("dosage", "the scheduled dose"),
                room,
                drawer_message=f"Hello {patient}. Medication assistance has arrived in room {room}.",
                wait_seconds=20,
            )
            complete_robot_task(task_id, f"Medication request completed in room {room}.")
            return

        if task_type == "water_delivery":
            run_delivery_sequence(
                patient,
                "water",
                "a glass of water",
                room,
                drawer_message=f"Hello {patient}. Water delivery has arrived in room {room}.",
                wait_seconds=10,
            )
            complete_robot_task(task_id, f"Water request completed in room {room}.")
            return

        if task_type == "help_request":
            post_heartbeat(current_task="Emergency assist", is_moving=True, location=f"En route to {room}")
            speak(f"Emergency assist heading to room {room}.")
            path = navigate_to_room(room, send_command, SERVER_URL, USER_ID)
            post_heartbeat(current_task="Emergency assist on site", is_moving=False, location=room)
            speak(f"Emergency assistance has arrived for {patient}. Caregiver has been notified.")
            time.sleep(8)
            return_to_base(path, send_command)
            post_heartbeat(
                current_task="Idle",
                is_moving=False,
                location="Dock",
                current_stop_index=0,
                remaining_stops=0,
                estimated_remaining_seconds=0,
            )
            complete_robot_task(task_id, f"Emergency assistance completed for room {room}.")
            return

        complete_robot_task(task_id, f"Unsupported task type skipped: {task_type}")
    except Exception as error:
        fail_robot_task(task_id, str(error))
        raise


def fetch_next_task():
    response = requests.get(f"{SERVER_URL}/api/robot/queue/{USER_ID}", timeout=10)
    response.raise_for_status()
    return response.json().get("task")


def main():
    speak("Jacob medical system online. Monitoring control center for requests.")
    post_heartbeat(current_task="Idle", is_moving=False, location="Dock", drawer_open=False)
    print(f"System online. Monitoring {SERVER_URL}")

    while True:
        try:
            task = fetch_next_task()

            if task:
                print(f"\nQueued task received: {task.get('task_type')}")
                handle_robot_task(task)
            else:
                batch = fetch_due_batch()
                if batch.get("stops"):
                    execute_scheduled_batch(batch)
                else:
                    post_heartbeat(
                        current_task="Idle",
                        is_moving=False,
                        location="Dock",
                        drawer_open=False,
                        current_stop_index=0,
                        remaining_stops=0,
                        estimated_remaining_seconds=0,
                    )
                    if batch.get("due_task_count") and batch.get("unroutable_tasks"):
                        print("\nDue medicines found, but no valid mapped route is available yet.")
                    sys.stdout.write("\rWaiting for commands... ")
                    sys.stdout.flush()

        except Exception as error:
            print(f"\nConnection or execution error: {error}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping Jacob System. Goodbye.")
