# Booking Payload Implementation Plan

I reviewed the `logs\runlog_20260701_155525.log` and the `form.html` source. Here is the finalized plan to implement the final booking step, incorporating your feedback.

## 1. Login Failure Investigation & Logging

The logs clearly show why the login returned a `401 Unauthorized`: the NopeCha API returned an error stating that the feature is unavailable for your current plan. Because it failed, the script sent an empty `g-recaptcha-response` to the login API, which resulted in the 401 error. 

**Action:** We will proceed with the implementation "blind" and test once the NopeCha plan is upgraded. We will also enhance the logging in both `operator.py` and `captcha_service.py` to ensure that **all** requests and responses (headers, payloads, statuses) sent to NopeCha and the portal are thoroughly logged to aid in future debugging.

## 2. Final Booking Payload Construction

By inspecting `RnD\sample-booking-form\form.html`, I successfully reverse-engineered the required fields for the final booking step. The booking API expects `application/x-www-form-urlencoded` form data.

The payload needs to include:
- `vac`: `138` (from environment)
- `type`: `26` (from environment - Long-Term Type D)
- `bookingfor`: `0` (Individual - from environment)
- `email`: Applicant's email (from environment)
- `phonenumberprefix[id]`: `197` (Pakistan - from environment)
- `phonenumber`: Applicant's phone number (from environment)
- `applicants[][surname]`: Surname (from environment)
- `applicants[][firstname]`: First Name (from environment)
- `applicants[][dateofbirth]`: DOB (from environment)
- `applicants[][passportnumber]`: Passport Number (from environment)
- `applicants[][traveldocumentvaliduntil]`: Passport Expiry (from environment)
- `applicants[][gender[id]]`: `2` (Male), `1` (Female) (from environment)
- `applicants[][nationality[id]]]`: Nationality ID (from environment)
- `otp`: The SMS OTP
- `g-recaptcha-response`: The solved captcha token for the booking step

## 3. Future Work: Multi-Applicant Config

Currently, all applicant data (Name, DOB, Email, etc.) will be stored in the `.env` file for immediate testing. 

**Future Enhancement:** Eventually, these fields will be migrated to a structured configuration file (like a `.csv` or JSON format) to allow the Operator Agent to read multiple applicants' data and iterate over them sequentially. The current implementation will be designed to easily accept a dictionary of applicant data to facilitate this transition later without needing core rewrites.

## Proposed Changes

### [MODIFY] [operator.py](file:///f:/Playgrounds/bookingbot/ttttt/operator.py) & [captcha_service.py](file:///f:/Playgrounds/bookingbot/ttttt/captcha_service.py)
1. Update `book_appointment` to construct the payload dictionary using the exact field names found in the HTML form and send it as `data=` (form-encoded).
2. Read the `type` and `bookingfor` dynamically from environment variables.
3. Add deep logging for all API requests and responses.

### [MODIFY] [.env.example](file:///f:/Playgrounds/bookingbot/ttttt/.env.example)
Add missing applicant fields: Email, First Name, Surname, Phone Number, Phone Prefix, Nationality ID, Type, and Booking For.
