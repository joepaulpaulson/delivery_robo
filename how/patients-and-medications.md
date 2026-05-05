# Patients And Medications

Patient and medication data are central to the whole app.

## Core Models

The main models are:

- `Patient` in [app.py](D:/Jewellery-app/delivery_robo/app.py:132)
- `Medication` in [app.py](D:/Jewellery-app/delivery_robo/app.py:145)
- `PatientHistory` in [app.py](D:/Jewellery-app/delivery_robo/app.py:167)

Each patient belongs to one admin user and includes:

- name
- room number
- optional age
- optional gender
- optional bed number
- optional emergency notes

Each medication belongs to one patient and includes:

- name
- dosage
- stock
- max stock
- schedule time
- instructions
- frequency
- days
- last taken

## Patient Management Routes

The main patient management routes are:

- `GET /patients` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1723)
- `POST /patients/create` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1732)
- `POST /patients/<patient_id>/update` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1768)
- `POST /patients/<patient_id>/delete` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1804)

The main UI is [patients.html](D:/Jewellery-app/delivery_robo/templates/patients.html:1).

## Medication Creation

Medication creation is centralized in:

- `create_medication_for_patient(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:901)

This function:

1. validates name and time
2. normalizes dosage and instructions
3. creates the medication record
4. logs an activity entry

Medication can be created from:

- the patient management page
- the setup flow
- the dashboard “Add Task” API

## Patient History Notes

Caretaker notes and symptom tags are stored through:

- `create_patient_history(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:492)
- `POST /patients/<patient_id>/history-note` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1827)

This history is later shown in both the admin and patient views.

## Linked Patient Accounts

Patient login credentials can be created or updated while managing a patient profile.

The helper for this is:

- `create_patient_account(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1488)

That allows each patient to have their own portal login tied to the same patient record.
