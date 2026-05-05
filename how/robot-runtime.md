# Robot Runtime

The robot-side runtime lives mainly in:

- [Robo_programs/main.py](D:/Jewellery-app/delivery_robo/Robo_programs/main.py:1)
- [Robo_programs/navigation.py](D:/Jewellery-app/delivery_robo/Robo_programs/navigation.py:1)
- [Robo_programs/robot_controller.ino](D:/Jewellery-app/delivery_robo/Robo_programs/robot_controller.ino:1)

## Main Loop

The robot process starts in `main()` in [Robo_programs/main.py](D:/Jewellery-app/delivery_robo/Robo_programs/main.py:453).

Its loop is:

1. post initial idle heartbeat
2. poll the queued task API
3. if a queued task exists, execute it
4. otherwise ask for due scheduled medicine batch
5. sleep and repeat

## Robot Polling APIs

The robot talks to these backend endpoints:

- `GET /api/robot/queue/<user_id>` for direct queued tasks
- `GET /api/robot/check/<user_id>` for scheduled medication batches
- `POST /api/robot/heartbeat/<user_id>` for live state updates
- `POST /api/robot/task/complete` when a queued task succeeds
- `POST /api/robot/task/fail` when a queued task fails
- `POST /api/robot/mission_log` for readable mission events
- `POST /api/robot/complete` when medication has been dispensed

The route implementations are in [app.py](D:/Jewellery-app/delivery_robo/app.py:2450), [app.py](D:/Jewellery-app/delivery_robo/app.py:2483), [app.py](D:/Jewellery-app/delivery_robo/app.py:2496), [app.py](D:/Jewellery-app/delivery_robo/app.py:2540), [app.py](D:/Jewellery-app/delivery_robo/app.py:2575), and [app.py](D:/Jewellery-app/delivery_robo/app.py:2589).

## Task Execution

Queued tasks are handled by:

- `handle_robot_task(task)` in [Robo_programs/main.py](D:/Jewellery-app/delivery_robo/Robo_programs/main.py:366)

This function supports:

- direct robot commands
- room navigation
- medicine delivery
- water delivery
- help requests

## Navigation

Navigation logic is in:

- `navigate_to_room(...)` in [Robo_programs/navigation.py](D:/Jewellery-app/delivery_robo/Robo_programs/navigation.py:194)
- `execute_path_cells(...)` in [Robo_programs/navigation.py](D:/Jewellery-app/delivery_robo/Robo_programs/navigation.py:168)

The navigation layer:

1. fetches the saved map from the server
2. computes a grid path
3. converts path cells into `L`, `R`, and `F` commands
4. sends those commands to Arduino through serial

## Serial Command Protocol

The Raspberry Pi or host Python process sends single-character commands to Arduino:

- `F` forward
- `B` backward
- `L` left
- `R` right
- `S` stop
- `O` open drawer
- `C` close drawer

Those are implemented in [robot_controller.ino](D:/Jewellery-app/delivery_robo/Robo_programs/robot_controller.ino:1).

## Heartbeat And Robot State

Live robot state is stored in:

- `RobotState` in [app.py](D:/Jewellery-app/delivery_robo/app.py:192)

Heartbeat updates include fields such as:

- current task
- location
- whether the robot is moving
- whether the drawer is open
- current stop index
- remaining stops
- estimated remaining seconds

That state is exposed to the dashboard through:

- `GET /api/robot/status` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2088)
