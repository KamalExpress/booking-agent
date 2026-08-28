# GVC Portal: Complete API Endpoints & Request/Response Specification (HAR Baseline)

This document provides the definitive developer reference for all GVC Greek Visa Application Center (`pk-gr-services.gvcworld.eu`) endpoints reverse-engineered from verified HAR recordings.

---

## 1. Authentication & Session Initialization

### `POST /api/v1/auth/login`
* **Purpose:** Authenticate portal user and establish session cookies (`JSESSIONID`, `AWSALB`, `incap_ses_*`).
* **Content-Type:** `application/json; charset=UTF-8`
* **Request Payload:**
  ```json
  {
    "username": "portal_user@example.com",
    "password": "UserPassword123!",
    "g-recaptcha-response": "03AFcWeA..."
  }
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "message": "Login successful",
    "token": "fake-jwt-or-session-token",
    "returnobject": {
      "id": 931995,
      "username": "portal_user@example.com",
      "firstname": "AMR",
      "lastname": "SHAH"
    }
  }
  ```
* **Error Response (HTTP 401 / 403):**
  ```json
  {
    "message": "Bad credentials",
    "code": "UNAUTHORIZED"
  }
  ```

---

## 2. Booking Page Navigation & Hidden State Extraction

### `POST /appointments/add` (or `GET /appointments/add`)
* **Purpose:** Loads the appointment booking form HTML and seeds the server-side booking session with the hidden `otpuser` state token.
* **Headers:** Standard browser document fetch / XMLHttpRequest.
* **Success Response (HTTP 200 HTML):**
  Contains the hidden input element required for final booking:
  ```html
  <form id="appointment" class="classic" onsubmit="return false">
    <input type="hidden" name="otpuser" id="otpuser" value="User{id=931995, username=portal_user@example.com, password=5e80b93c0a7aef7bad58901b480ea650b6212292, firstname=AMR, lastname=SHAH, email=portal_user@example.com, country=Vcountry{id=19, name=PAKISTAN}, vac=Vac{id=137, name=Islamabad Visa Application Center for Greece}, roles=null, userroles=[eu.ubitech.gvcw.repository.domain.UserRole@1d6e9e2c]}"/>
  </form>
  ```

---

## 3. Slot Availability Search

### `PUT /api/v1/periodslot/slots`
* **Purpose:** Query available appointment slots for a specific date and visa center.
* **Content-Type:** `application/json; charset=UTF-8`
* **Request Payload:**
  ```json
  {
    "datefrom": "03/09/2026",
    "type": 26,
    "bookingfor": 0,
    "members": 1,
    "method": 1,
    "travelpurposes": -1,
    "howmanyapplicantsareunder12": 0,
    "appointmentId": "undefined",
    "id": 0,
    "vac": {
      "id": 138
    }
  }
  ```
  *Note:* `type: 26` corresponds to Long-Term Type D Seasonal Employment. `vac.id: 138` (Islamabad), `137` (Lahore), `139` (Karachi).
* **Success Response with Slots (HTTP 200):**
  ```json
  {
    "code": "SUCCESS",
    "message": "",
    "returnobject": {
      "slots": [
        {
          "id": null,
          "periodid": 14098,
          "timestamp": null,
          "date": null,
          "starttime": "09:30",
          "endtime": "09:45",
          "numofavailableslots": 1,
          "isavailable": true,
          "isselectable": true
        }
      ]
    }
  }
  ```

---

## 4. SMS OTP Triggering

### `POST /api/v1/onetimepassword/sendOtpBookAppointment/{phone}/{prefix_id}`
* **Purpose:** Instructs the GVC backend to generate and dispatch an SMS OTP to the applicant's phone number via Gerry's gateway.
* **URL Path Parameters:**
  - `phone`: Mobile number stripped of leading 0 (e.g. `3345112969`).
  - `prefix_id`: Database ID of the country calling code (`197` for Pakistan +92).
* **Headers:**
  ```http
  Accept: */*
  Referer: https://pk-gr-services.gvcworld.eu/appointments/add
  X-Requested-With: XMLHttpRequest
  Content-Length: 0
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "message": "OTP code sent by SMS",
    "returnobject": null,
    "code": "SUCCESS"
  }
  ```
* **Failure Response (HTTP 200 / 400):**
  ```json
  {
    "message": "Invalid phone number or max OTP limit reached",
    "returnobject": null,
    "code": "ERROR"
  }
  ```

---

## 5. Final Appointment Booking Submission

### `POST /api/v1/appointments`
* **Purpose:** Submits the applicant details, selected slot, solved captcha token, and verified OTP to confirm the appointment.
* **Content-Type:** `application/json; charset=UTF-8`
* **Request Payload Schema:**
  ```json
  {
    "otpuser": "User{id=931995, username=portal_user@example.com, ...}",
    "vac": "138",
    "type": "26",
    "bookingfor": "0",
    "members": "1",
    "email": "applicant@example.com",
    "phonenumberprefix": {
      "id": "197"
    },
    "phonenumber": "3345112969",
    "applicants": [
      {
        "surname": "KHAN",
        "firstname": "ZAHID",
        "dateofbirth": "15/08/1992",
        "passportnumber": "PK9876543",
        "traveldocumentvaliduntil": "20/12/2030",
        "gender": {
          "id": "1"
        },
        "nationality": {
          "id": "197"
        },
        "periodslotid": "2528256"
      }
    ],
    "datefrom": "03/09/2026",
    "selectedtime": "09:30",
    "appointmentmethod": "1",
    "submitinfo": "on",
    "submissionMsgCheck": "Make sure that you have checked the required checkbox",
    "onetimepassword": "55613",
    "g-recaptcha-response": "0cAFcWeA..."
  }
  ```

* **Success Response (HTTP 200):**
  ```json
  {
    "message": "Success",
    "returnobject": {
      "reference": "GVCW-GR-ISB-20261022-8899",
      "appointmentId": 2528256,
      "status": "CONFIRMED"
    },
    "code": "SUCCESS"
  }
  ```

* **Invalid OTP Response (HTTP 200):**
  ```json
  {
    "message": "Mismatch OTP. Please, try again",
    "returnobject": null,
    "code": "INVALID"
  }
  ```

* **Slot Taken / Expired Response (HTTP 200):**
  ```json
  {
    "message": "The selected time slot is no longer available.",
    "returnobject": null,
    "code": "SLOT_UNAVAILABLE"
  }
  ```
