# AI And Voice

This app supports both AI symptom checking and speech-driven requests.

## AI Symptom Checking

There are two AI symptom-check endpoints:

- `POST /api/ai/symptom-check` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2145)
- `POST /patient/api/ai/symptom-check` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2398)

Both flows:

1. accept a symptom text payload
2. check for emergency keywords
3. optionally send emergency email alerts
4. build a medical-context prompt
5. call the configured Gemini model
6. log the activity

The medication-aware prompt context comes from:

- `get_user_context(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:416)

Emergency keyword matching comes from:

- `contains_emergency(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1183)

## Voice Command Processing

Voice input is handled separately for admins and patients.

Admin voice endpoint:

- `POST /api/voice/process` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2197)

Patient voice endpoint:

- `POST /patient/api/voice/process` in [app.py](D:/Jewellery-app/delivery_robo/app.py:2380)

These call:

- `interpret_command_text(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1051)
- `interpret_patient_command_text(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1134)

## What Voice Can Trigger

Current voice flows are designed to trigger high-level actions such as:

- medicine requests
- water requests
- help/SOS requests
- room navigation by room number

Admin voice no longer allows direct manual motion commands in the current frontend flow.

## Frontend Files

Voice and AI UI behavior is implemented in:

- [static/js/script.js](D:/Jewellery-app/delivery_robo/static/js/script.js:244)
- [static/js/patient.js](D:/Jewellery-app/delivery_robo/static/js/patient.js:83)
- [index.html](D:/Jewellery-app/delivery_robo/templates/index.html:141)
- [patient_dashboard.html](D:/Jewellery-app/delivery_robo/templates/patient_dashboard.html:276)
