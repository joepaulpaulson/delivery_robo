import os
import sys
import time

import requests
import serial
from gtts import gTTS

from navigation import (
    DEFAULT_HEADING,
    deserialize_path_cells,
    execute_commands,
    execute_path_cells,
    route_to_room,
    return_to_base,
)


SERVER_URL = os.environ.get("ROBOT_SERVER_URL", "http://192.168.18.62:5000")
USER_ID = int(os.environ.get("ROBOT_USER_ID", "1"))
PORT_NAME = os.environ.get("ROBOT_PORT", "/dev/ttyUSB0")
POLL_INTERVAL_SECONDS = int(os.environ.get("ROBOT_POLL_INTERVAL_SECONDS", "3"))
SERIAL_BAUD_RATE = int(os.environ.get("ROBOT_SERIAL_BAUD", "9600"))
COMMAND_SETTLE_SECONDS = float(os.environ.get("ROBOT_COMMAND_SETTLE_SECONDS", "0.35"))
WAIT_HEARTBEAT_INTERVAL_SECONDS = float(
    os.environ.get("ROBOT_WAIT_HEARTBEAT_INTERVAL_SECONDS", "1")
)
MEDICINE_DELIVERY_WAIT_SECONDS = int(
    os.environ.get("ROBOT_MEDICINE_DELIVERY_WAIT_SECONDS", "20")
)
WATER_DELIVERY_WAIT_SECONDS = int(
    os.environ.get("ROBOT_WATER_DELIVERY_WAIT_SECONDS", "10")
)
HELP_REQUEST_WAIT_SECONDS = int(os.environ.get("ROBOT_HELP_REQUEST_WAIT_SECONDS", "8"))
SCHEDULE_STOP_WAIT_SECONDS = int(os.environ.get("ROBOT_SCHEDULE_STOP_WAIT_SECONDS", "18"))


try:
    arduino = serial.Serial(PORT_NAME, SERIAL_BAUD_RATE, timeout=1)
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


def read_controller_feedback(timeout_seconds=0.25):
    deadline = time.time() + timeout_seconds
    messages = []
    while time.time() < deadline:
        if arduino.in_waiting:
            raw_line = arduino.readline().decode(errors="ignore").strip()
            if raw_line:
                messages.append(raw_line)
        else:
            time.sleep(0.02)
    return messages


def send_controller_signal(command):
    arduino.write(command.encode())
    feedback = read_controller_feedback()
    for message in feedback:
        print(f"Controller: {message}")
    return feedback


def send_command(command, duration):
    duration = max(float(duration), 0.0)
    print(f"Sending '{command}' for {duration:.2f} second(s)...")
    send_controller_signal(command)
    time.sleep(duration)
    send_controller_signal("S")
    time.sleep(COMMAND_SETTLE_SECONDS)


def post_heartbeat(**payload):
    try:
        requests.post(
            f"{SERVER_URL}/api/robot/heartbeat/{USER_ID}",
            json=payload,
            timeout=10,
        )
    except Exception as error:
        print(f"Heartbeat failed: {error}")


def post_robot_state(
    *,
    current_task="Idle",
    is_moving=False,
    location="Dock",
    drawer_open=False,
    current_stop_index=0,
    remaining_stops=0,
    estimated_remaining_seconds=0,
):
    post_heartbeat(
        current_task=current_task,
        is_moving=is_moving,
        location=location,
        drawer_open=drawer_open,
        current_stop_index=current_stop_index,
        remaining_stops=remaining_stops,
        estimated_remaining_seconds=max(int(estimated_remaining_seconds), 0),
    )


def wait_with_heartbeat(
    wait_seconds,
    *,
    current_task,
    location,
    current_stop_index=0,
    remaining_stops=0,
    estimated_after_wait=0,
):
    wait_seconds = max(int(wait_seconds), 0)
    deadline = time.time() + wait_seconds

    while True:
        remaining_wait = max(int(round(deadline - time.time())), 0)
        post_robot_state(
            current_task=current_task,
            is_moving=False,
            location=location,
            drawer_open=False,
            current_stop_index=current_stop_index,
            remaining_stops=remaining_stops,
            estimated_remaining_seconds=estimated_after_wait + remaining_wait,
        )
        if remaining_wait <= 0:
            break
        time.sleep(min(WAIT_HEARTBEAT_INTERVAL_SECONDS, remaining_wait))


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


def route_duration_seconds(route):
    return int(round(sum(duration for _, duration in route.get("commands") or [])))


def signal_virtual_drawer(action, location, message):
    action = action.lower().strip()
    if action not in {"open", "close"}:
        raise ValueError(f"Unsupported drawer action: {action}")

    command = "O" if action == "open" else "C"
    print(f"Drawer action ({action}) at {location}: {message}")
    send_controller_signal(command)
    post_mission_log(
        "Robot Drawer Notice",
        f"{action.title()} request at {location}: {message}",
    )


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
        signal_virtual_drawer("open", "Dock", "Manual drawer-open command received.")
    elif command == "close_drawer":
        signal_virtual_drawer("close", "Dock", "Manual drawer-close command received.")
    elif command == "emergency":
        send_controller_signal("S")
        speak("Emergency stop activated.")
    else:
        send_controller_signal("S")

    post_robot_state(
        current_task=f"Executed {command}",
        is_moving=False,
        location="Dock",
        drawer_open=False,
    )


def run_delivery_sequence(
    patient_name,
    item_name,
    dosage,
    room,
    *,
    drawer_message,
    wait_seconds,
):
    print(f"Starting delivery: {item_name} for {patient_name} in room {room}")
    route = route_to_room(
        room,
        server_url=SERVER_URL,
        user_id=USER_ID,
        initial_heading=DEFAULT_HEADING,
    )
    outbound_seconds = route_duration_seconds(route)

    post_robot_state(
        current_task=f"Delivering {item_name}",
        is_moving=True,
        location=f"En route to {room}",
        estimated_remaining_seconds=outbound_seconds + wait_seconds,
    )
    speak(f"Delivering {item_name} for {patient_name} to room {room}.")
    execute_commands(route["commands"], send_command)

    post_robot_state(
        current_task=f"At {room}",
        is_moving=False,
        location=room,
        estimated_remaining_seconds=wait_seconds,
    )
    speak(drawer_message)
    signal_virtual_drawer(
        "open",
        room,
        f"{item_name.title()} ready for {patient_name}. Dosage/info: {dosage}.",
    )

    print(f"Waiting {wait_seconds} seconds at room {room}...")
    wait_with_heartbeat(
        wait_seconds,
        current_task=f"Serving {item_name}",
        location=room,
        estimated_after_wait=0,
    )

    signal_virtual_drawer(
        "close",
        room,
        f"Completed {item_name} stop for {patient_name}.",
    )
    post_robot_state(
        current_task="Returning to dock",
        is_moving=True,
        location=f"Leaving {room}",
        estimated_remaining_seconds=outbound_seconds,
    )
    speak("Task complete. Returning to the dock.")
    return_to_base(
        route,
        send_command,
        current_heading=route["final_heading"],
        target_heading=DEFAULT_HEADING,
    )
    post_robot_state()


def remaining_batch_travel_seconds(batch, stop_zero_based):
    remaining = 0
    for stop in (batch.get("stops") or [])[stop_zero_based:]:
        remaining += int(stop.get("travel_seconds") or 0)
    remaining += int((batch.get("return_path") or {}).get("travel_seconds") or 0)
    return remaining


def remaining_batch_service_seconds(stop_count):
    return stop_count * SCHEDULE_STOP_WAIT_SECONDS


def remaining_batch_before_departure(batch, stop_zero_based):
    stops_left = len((batch.get("stops") or [])[stop_zero_based:])
    return remaining_batch_travel_seconds(batch, stop_zero_based) + remaining_batch_service_seconds(
        stops_left
    )


def remaining_batch_after_arrival(batch, stop_zero_based):
    later_stops = len((batch.get("stops") or [])[stop_zero_based + 1 :])
    return (
        SCHEDULE_STOP_WAIT_SECONDS
        + remaining_batch_travel_seconds(batch, stop_zero_based + 1)
        + remaining_batch_service_seconds(later_stops)
    )


def remaining_batch_after_service(batch, next_stop_zero_based):
    later_stops = len((batch.get("stops") or [])[next_stop_zero_based:])
    return remaining_batch_travel_seconds(batch, next_stop_zero_based) + remaining_batch_service_seconds(
        later_stops
    )


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
            post_robot_state(current_task="Waiting for mapped route")
        return False

    batch_id = batch.get("batch_id", "batch")
    unroutable_tasks = batch.get("unroutable_tasks") or []
    if unroutable_tasks:
        warning_rooms = ", ".join(
            sorted({item.get("room") for item in unroutable_tasks if item.get("room")})
        )
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

    heading = DEFAULT_HEADING
    post_robot_state(
        current_task=f"Medication batch {batch_id}",
        is_moving=False,
        location="Dock",
        remaining_stops=total_stops,
        estimated_remaining_seconds=remaining_batch_before_departure(batch, 0),
    )

    for stop_index, stop in enumerate(stops, start=1):
        stop_zero_based = stop_index - 1
        room = stop.get("room", "Unknown Room")
        deliveries = stop.get("patient_deliveries") or []
        travel_path = deserialize_path_cells(stop.get("path_cells"))

        if not travel_path:
            raise ValueError(f"Batch stop {stop_index} for room {room} has no path cells.")

        post_robot_state(
            current_task=f"Medication batch stop {stop_index}/{total_stops}",
            is_moving=True,
            location=f"En route to {room}",
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_zero_based,
            estimated_remaining_seconds=remaining_batch_before_departure(
                batch,
                stop_zero_based,
            ),
        )
        speak(f"Heading to room {room}. Stop {stop_index} of {total_stops}.")
        _, heading = execute_path_cells(
            travel_path,
            send_command,
            initial_heading=heading,
        )

        post_robot_state(
            current_task=f"Serving room {room}",
            is_moving=False,
            location=room,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_remaining_seconds=remaining_batch_after_arrival(
                batch,
                stop_zero_based,
            ),
        )

        patient_names = ", ".join(
            sorted({delivery.get("patient", "the patient") for delivery in deliveries})
        )
        speak(f"Arrived at room {room}. Delivering medication for {patient_names}.")
        signal_virtual_drawer(
            "open",
            room,
            f"Medication stop for {patient_names} in room {room}.",
        )
        wait_with_heartbeat(
            SCHEDULE_STOP_WAIT_SECONDS,
            current_task=f"Serving room {room}",
            location=room,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_after_wait=remaining_batch_after_service(batch, stop_index),
        )

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

        signal_virtual_drawer(
            "close",
            room,
            f"Completed medication stop for room {room}.",
        )
        post_robot_state(
            current_task=f"Completed room {room}",
            is_moving=False,
            location=room,
            current_stop_index=stop_index,
            remaining_stops=total_stops - stop_index,
            estimated_remaining_seconds=remaining_batch_after_service(batch, stop_index),
        )

    return_path = deserialize_path_cells((batch.get("return_path") or {}).get("path_cells"))
    return_seconds = int((batch.get("return_path") or {}).get("travel_seconds") or 0)
    if return_path:
        post_robot_state(
            current_task="Returning to dock",
            is_moving=True,
            location="Returning to base",
            current_stop_index=total_stops,
            remaining_stops=0,
            estimated_remaining_seconds=return_seconds,
        )
        speak("Medication round complete. Returning to the dock.")
        _, heading = execute_path_cells(
            return_path,
            send_command,
            initial_heading=heading,
        )
        return_to_base(
            {"path_cells": [(0, 0)], "commands": [], "final_heading": heading},
            send_command,
            current_heading=heading,
            target_heading=DEFAULT_HEADING,
        )

    post_robot_state()
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
            route = route_to_room(
                room,
                server_url=SERVER_URL,
                user_id=USER_ID,
                initial_heading=DEFAULT_HEADING,
            )
            post_robot_state(
                current_task=f"Navigating to {room}",
                is_moving=True,
                location=f"En route to {room}",
                estimated_remaining_seconds=route_duration_seconds(route),
            )
            execute_commands(route["commands"], send_command)
            speak(f"Arrived at room {room}. Returning to dock.")
            return_to_base(
                route,
                send_command,
                current_heading=route["final_heading"],
                target_heading=DEFAULT_HEADING,
            )
            post_robot_state()
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
                wait_seconds=MEDICINE_DELIVERY_WAIT_SECONDS,
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
                wait_seconds=WATER_DELIVERY_WAIT_SECONDS,
            )
            complete_robot_task(task_id, f"Water request completed in room {room}.")
            return

        if task_type == "help_request":
            route = route_to_room(
                room,
                server_url=SERVER_URL,
                user_id=USER_ID,
                initial_heading=DEFAULT_HEADING,
            )
            post_robot_state(
                current_task="Emergency assist",
                is_moving=True,
                location=f"En route to {room}",
                estimated_remaining_seconds=route_duration_seconds(route)
                + HELP_REQUEST_WAIT_SECONDS,
            )
            speak(f"Emergency assist heading to room {room}.")
            execute_commands(route["commands"], send_command)
            post_robot_state(
                current_task="Emergency assist on site",
                is_moving=False,
                location=room,
                estimated_remaining_seconds=HELP_REQUEST_WAIT_SECONDS,
            )
            speak(f"Emergency assistance has arrived for {patient}. Caregiver has been notified.")
            wait_with_heartbeat(
                HELP_REQUEST_WAIT_SECONDS,
                current_task="Emergency assist on site",
                location=room,
            )
            return_to_base(
                route,
                send_command,
                current_heading=route["final_heading"],
                target_heading=DEFAULT_HEADING,
            )
            post_robot_state()
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
    post_robot_state()
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
                    post_robot_state()
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
