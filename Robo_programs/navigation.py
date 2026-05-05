import sys
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config import Config


STEP_DURATION = float(Config.GRID_STEP_SECONDS)
TURN_DURATION = 0.8
DEFAULT_HEADING = "N"
HEADINGS = ["N", "E", "S", "W"]

FALLBACK_ROUTES = {
    "A-101": [("F", 5.0)],
    "A-102": [("F", 7.0), ("L", 1.0), ("F", 3.0)],
    "B-201": [("F", 10.0), ("R", 2.0)],
}


def reverse_command(command):
    if command == "F":
        return "B"
    if command == "B":
        return "F"
    if command == "L":
        return "R"
    if command == "R":
        return "L"
    return "S"


def turn_instructions(current_heading, target_heading):
    current_index = HEADINGS.index(current_heading)
    target_index = HEADINGS.index(target_heading)
    delta = (target_index - current_index) % 4

    if delta == 0:
        return []
    if delta == 1:
        return ["R"]
    if delta == 2:
        return ["R", "R"]
    return ["L"]


def heading_after_commands(commands, initial_heading=DEFAULT_HEADING):
    heading = initial_heading
    for command, _ in commands:
        if command == "R":
            heading = HEADINGS[(HEADINGS.index(heading) + 1) % len(HEADINGS)]
        elif command == "L":
            heading = HEADINGS[(HEADINGS.index(heading) - 1) % len(HEADINGS)]
    return heading


def fetch_navigation_map(server_url, user_id):
    response = requests.get(f"{server_url}/api/robot/map/{user_id}", timeout=10)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError("Navigation map request did not succeed.")
    return payload


def neighbors(node, cols, rows):
    x, y = node
    points = []
    if x < cols - 1:
        points.append((x + 1, y))
    if x > 0:
        points.append((x - 1, y))
    if y < rows - 1:
        points.append((x, y + 1))
    if y > 0:
        points.append((x, y - 1))
    return points


def find_path(grid, start, goal):
    cols = len(grid)
    rows = len(grid[0]) if cols else 0
    if not cols or not rows:
        return []
    if not (0 <= start[0] < cols and 0 <= start[1] < rows):
        return []
    if not (0 <= goal[0] < cols and 0 <= goal[1] < rows):
        return []

    frontier = [{"point": start, "g": 0, "h": 0, "f": 0, "parent": None}]
    closed = set()

    while frontier:
        current_index = min(range(len(frontier)), key=lambda index: frontier[index]["f"])
        current = frontier.pop(current_index)
        if current["point"] == goal:
            path = []
            cursor = current
            while cursor:
                path.append(cursor["point"])
                cursor = cursor["parent"]
            return list(reversed(path))

        closed.add(current["point"])

        for neighbor in neighbors(current["point"], cols, rows):
            x, y = neighbor
            if neighbor in closed or grid[x][y] == 1:
                continue

            tentative_g = current["g"] + 1
            existing = next((item for item in frontier if item["point"] == neighbor), None)

            if existing and tentative_g >= existing["g"]:
                continue

            h_cost = abs(goal[0] - x) + abs(goal[1] - y)
            node = {
                "point": neighbor,
                "g": tentative_g,
                "h": h_cost,
                "f": tentative_g + h_cost,
                "parent": current,
            }

            if existing:
                frontier.remove(existing)
            frontier.append(node)

    return []


def build_command_sequence(path_cells, initial_heading=DEFAULT_HEADING):
    if len(path_cells) < 2:
        return [], initial_heading

    heading = initial_heading
    commands = []
    direction_lookup = {
        (0, -1): "N",
        (1, 0): "E",
        (0, 1): "S",
        (-1, 0): "W",
    }

    for current, next_point in zip(path_cells, path_cells[1:]):
        delta = (next_point[0] - current[0], next_point[1] - current[1])
        target_heading = direction_lookup.get(delta)
        if not target_heading:
            continue

        for turn in turn_instructions(heading, target_heading):
            commands.append((turn, TURN_DURATION))
        commands.append(("F", STEP_DURATION))
        heading = target_heading

    return commands, heading


def execute_commands(commands, send_command):
    for command, duration in commands:
        send_command(command, duration)


def deserialize_path_cells(path_cells):
    return [(int(point["x"]), int(point["y"])) for point in path_cells or []]


def estimate_path_seconds(path_cells):
    return max(len(path_cells) - 1, 0) * STEP_DURATION


def execute_path_cells(path_cells, send_command, initial_heading=DEFAULT_HEADING):
    commands, final_heading = build_command_sequence(
        path_cells,
        initial_heading=initial_heading,
    )
    execute_commands(commands, send_command)
    return commands, final_heading


def build_route_from_path(path_cells, *, initial_heading=DEFAULT_HEADING, source="map"):
    commands, final_heading = build_command_sequence(
        path_cells,
        initial_heading=initial_heading,
    )
    return {
        "source": source,
        "path_cells": path_cells,
        "commands": commands,
        "final_heading": final_heading,
    }


def fallback_route_for_room(room, initial_heading=DEFAULT_HEADING):
    commands = FALLBACK_ROUTES.get(room)
    if not commands:
        raise ValueError(f"No mapped or fallback route found for room {room}.")

    final_heading = heading_after_commands(commands, initial_heading=initial_heading)
    return {
        "source": "fallback",
        "path_cells": [],
        "commands": commands,
        "final_heading": final_heading,
    }


def route_to_room(room, server_url=None, user_id=None, initial_heading=DEFAULT_HEADING):
    if server_url and user_id:
        payload = fetch_navigation_map(server_url, user_id)
        grid = payload.get("grid") or []
        rooms = payload.get("rooms") or {}
        base = payload.get("base") or {"x": 2, "y": 2}
        target = rooms.get(room)

        if target and grid:
            start = (int(base.get("x", 2)), int(base.get("y", 2)))
            goal = (int(target.get("x")), int(target.get("y")))
            path_cells = find_path(grid, start, goal)
            if path_cells:
                return build_route_from_path(
                    path_cells,
                    initial_heading=initial_heading,
                    source="map",
                )
            raise ValueError(f"No valid mapped path found from base to room {room}.")

    return fallback_route_for_room(room, initial_heading=initial_heading)


def navigate_to_room(room, send_command, server_url=None, user_id=None, initial_heading=DEFAULT_HEADING):
    print(f"Navigation started for room: {room}")
    route = route_to_room(
        room,
        server_url=server_url,
        user_id=user_id,
        initial_heading=initial_heading,
    )
    print(f"Using {route['source']} route for {room}")
    execute_commands(route["commands"], send_command)
    print("Reached destination")
    return route


def return_to_base(route, send_command, current_heading, target_heading=DEFAULT_HEADING):
    print("Returning to base...")

    if route.get("path_cells"):
        return_path = list(reversed(route["path_cells"]))
        commands, heading_at_base = build_command_sequence(
            return_path,
            initial_heading=current_heading,
        )
    else:
        commands = [
            (reverse_command(command), duration)
            for command, duration in reversed(route.get("commands") or [])
        ]
        heading_at_base = heading_after_commands(commands, initial_heading=current_heading)

    execute_commands(commands, send_command)

    alignment_commands = [
        (turn, TURN_DURATION) for turn in turn_instructions(heading_at_base, target_heading)
    ]
    if alignment_commands:
        print(f"Aligning at base to heading {target_heading}")
        execute_commands(alignment_commands, send_command)
        heading_at_base = target_heading

    print("Returned to base")
    return {
        "commands": commands,
        "alignment_commands": alignment_commands,
        "final_heading": heading_at_base,
    }
