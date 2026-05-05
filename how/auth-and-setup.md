# Auth And Setup

This app has two main user roles:

- `ADMIN`
- `PATIENT`

The account model and role logic are defined in [app.py](D:/Jewellery-app/delivery_robo/app.py:105).

## Admin Login

Admin authentication uses:

- `GET/POST /login` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1539)
- `GET/POST /register` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1559)

After a successful login, the user is redirected based on role by `default_dashboard_for(account)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1518).

## Patient Login

Patient authentication uses:

- `GET/POST /patient/login` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1592)

Patient accounts are separate `Account` rows with:

- `role="PATIENT"`
- `patient_id=<linked patient>`

Patient account creation is handled by `create_patient_account(...)` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1488).

## Access Guards

The app uses two main access decorators:

- `admin_required` in [app.py](D:/Jewellery-app/delivery_robo/app.py:370)
- `patient_required` in [app.py](D:/Jewellery-app/delivery_robo/app.py:384)

These ensure each route sends the correct user type to the right dashboard.

## First-Time Setup

The initial caretaker setup flow is:

- `GET/POST /setup` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1620)

This flow:

1. accepts a batch of patients and medications
2. clears old linked patient data for that admin
3. creates new patients
4. creates medications for each patient
5. ensures robot state exists for the user

Templates involved:

- [setup.html](D:/Jewellery-app/delivery_robo/templates/setup.html:1)
- [login.html](D:/Jewellery-app/delivery_robo/templates/login.html:1)
- [register.html](D:/Jewellery-app/delivery_robo/templates/register.html:1)
- [patient_login.html](D:/Jewellery-app/delivery_robo/templates/patient_login.html:1)

## Logout

Logout is handled by:

- `GET /logout` in [app.py](D:/Jewellery-app/delivery_robo/app.py:1612)

It sends patients back to the patient login page and admins back to the admin login page.
