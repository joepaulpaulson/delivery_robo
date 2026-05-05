# Requests And Queue

This app uses a queue-based robot task system.

## Core Queue Model

Queued work is stored in:

- `RobotTask` in [app.py](D:/Jewellery-app/delivery_robo/app.py:215)

Each task can include:

- task type
- patient
- medication
- room number
- payload
- priority
- status

## Request Types

The main request types are:

- medicine delivery
- water delivery
- help request
- room navigation
- robot command

Helpers that create them:

- `create_request_for_patient(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:935)
- `create_dashboard_request(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:991)
- `create_navigation_task(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1029)
- `queue_robot_command_for_user(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1011)

## Queue API Endpoints

Admin request endpoints:

- `POST /api/request` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2293)
- `POST /api/emergency` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2316)
- `POST /api/robot/command` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2102)

Patient request endpoints:

- `POST /patient/api/request` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2344)
- `GET /patient/api/requests` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2367)

Robot polling endpoints:

- `GET /api/robot/queue/<user_id>` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2483)
- `POST /api/robot/task/complete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2496)
- `POST /api/robot/task/fail` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2540)

## Queue Dispatch Rules

The next queued task is selected by:

- `next_queued_robot_task(user_id)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1189)

Tasks are ordered by:

1. lowest priority number first
2. oldest created task first

When a task is claimed:

- status changes from `queued` to `dispatched`
- `claimed_at` is set
- robot state is updated

## Request Flow

The normal request flow is:

1. user presses a dashboard or patient request button
2. backend creates a `RobotTask`
3. robot polls the queue
4. robot executes the task
5. robot reports success or failure
6. app updates history and robot state

Relevant UIs:

- [index.html](D:/Jewellery-app/delivery_robo/templates/index.html:1)
- [patient_dashboard.html](D:/Jewellery-app/delivery_robo/templates/patient_dashboard.html:1)
