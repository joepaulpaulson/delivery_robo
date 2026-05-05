import requests
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config import Config


STEP_DURATION = float(Config.GRID_STEP_SECONDS)
TURN_DURATION = 0.8
DEFAULT_HEADING = "N"


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


def return_to_base(path, send_command):
    print("Retracing path to base...")
    for command, duration in reversed(path):
        send_command(reverse_command(command), duration)
    print("Returned to base")


def fetch_navigation_map(server_url, user_id):
    try:
        response = requests.get(f"{server_url}/api/robot/map/{user_id}", timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            return None
        return payload
    except Exception as error:
        print(f"Map fetch failed: {error}")
        return None


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


def turn_instructions(current_heading, target_heading):
    headings = ["N", "E", "S", "W"]
    current_index = headings.index(current_heading)
    target_index = headings.index(target_heading)
    delta = (target_index - current_index) % 4

    if delta == 0:
        return []
    if delta == 1:
        return ["R"]
    if delta == 2:
        return ["R", "R"]
    return ["L"]


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
    commands, final_heading = build_command_sequence(path_cells, initial_heading=initial_heading)
    execute_commands(commands, send_command)
    return commands, final_heading


def generate_map_route(room, server_url, user_id):
    payload = fetch_navigation_map(server_url, user_id)
    if not payload:
        return []

    grid = payload.get("grid") or []
    rooms = payload.get("rooms") or {}
    base = payload.get("base") or {"x": 2, "y": 2}
    target = rooms.get(room)

    if not target or not grid:
        return []

    start = (int(base.get("x", 2)), int(base.get("y", 2)))
    goal = (int(target.get("x")), int(target.get("y")))
    path = find_path(grid, start, goal)
    commands, _ = build_command_sequence(path)
    return commands


def navigate_to_room(room, send_command, server_url=None, user_id=None):
    print(f"Navigation started for room: {room}")

    if server_url and user_id:
        mapped_route = generate_map_route(room, server_url, user_id)
        if mapped_route:
            print(f"Using saved map route for {room}")
            execute_commands(mapped_route, send_command)
            print("Reached destination")
            return mapped_route

    routes = {
        "A-101": [("F", 5)],
        "A-102": [("F", 7), ("L", 1), ("F", 3)],
        "B-201": [("F", 10), ("R", 2)],
    }

    path = routes.get(room)
    if not path:
        print("Unknown room. Using fallback path.")
        path = [("F", 5)]

    execute_commands(path, send_command)
    print("Reached destination")
    return path
