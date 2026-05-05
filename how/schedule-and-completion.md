# Schedule And Completion

The schedule system is built directly from patient medications.

## Schedule Sources

The schedule payload is generated from medication rows using:

- `schedule_payload_for_user(user)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:724)
- `schedule_payload_for_patient(patient)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:754)
- `today_schedule_api_payload(user)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:787)

These functions convert medication records into dashboard-friendly task items.

## Schedule APIs

The main schedule APIs are:

- `GET /api/schedule` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1985)
- `GET /api/schedule/today` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1991)
- `POST /api/schedule/complete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1997)
- `POST /api/task/add` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2215)
- `POST /api/task/delete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2236)
- `POST /api/task/toggle` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2251)

## Completion Logic

When a medication is marked complete:

1. `last_taken` is set to today
2. stock is reduced by 1 if available
3. an activity log entry is created
4. a patient history entry is created

This happens in:

- `POST /api/schedule/complete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1997)
- `POST /api/task/toggle` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2251)
- `POST /api/robot/complete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2589)

## Robot Completion

The robot can also complete medicines automatically by calling:

- `POST /api/robot/complete`

That endpoint:

- marks the medicine as taken for today
- decrements stock
- writes activity log history
- updates patient history
- updates robot state

This is what connects the physical robot run back to the app schedule.

## Main UI

Relevant UI pages:

- [index.html](D:/Jewellery-app/delivery_robo/templates/index.html:1)
- [patient_dashboard.html](D:/Jewellery-app/delivery_robo/templates/patient_dashboard.html:1)
