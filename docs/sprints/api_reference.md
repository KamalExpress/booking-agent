# Visa Application Centers API Reference

This document catalogs the known API endpoints, payload configurations, and IDs for the GVCW Greece Visa booking portal.

## Appointment Types (`type` field)
The `type` field in the API payload determines the category of the appointment. Our system is robust enough to handle any of these. In future iterations, this value could be made dynamically selectable when creating an Assignment. 

The known values extracted from the portal are:
- `0` : Submission Schengen Visa (Short term – Type C)
- `2` : National visa (Long term - type D)
- `6` : Prime Time (optional service at an additional charge)
- `24`: Document Verification *(Note: This was found via network captures for specific VACs like 140, but isn't always in the standard HTML dropdown)*
- `26`: Long-Term Type D (Seasonal/Dependent Employment)

## Base Endpoint
`PUT https://pk-gr-services.gvcworld.eu/api/v1/periodslot/slots`

## Known Configurations

### 1. Lahore (Type 26)
- **VAC ID:** 138
- **Appointment Type:** 26 (Standard/Default)
```json
{
    "datefrom": "16/09/2026",
    "type": 26,
    "bookingfor": 0,
    "members": 1,
    "method": 1,
    "travelpurposes": -1,
    "howmanyapplicantsareunder12": 0,
    "appointmentId": "undefined",
    "id": 0,
    "vac": { "id": 138 }
}
```

### 2. Islamabad (Type 26)
- **VAC ID:** 137
- **Appointment Type:** 26 (Standard/Default)
```json
{
    "datefrom": "25/09/2026",
    "type": 26,
    "bookingfor": 0,
    "members": 1,
    "method": 1,
    "travelpurposes": -1,
    "howmanyapplicantsareunder12": 0,
    "appointmentId": "undefined",
    "id": 0,
    "vac": { "id": 137 }
}
```

### 3. Doc Verification ("Other Centers")
- **VAC ID:** 140
- **Appointment Type:** 24 (Doc Verification)
```json
{
    "datefrom": "20/09/2026",
    "type": 24,
    "bookingfor": 0,
    "members": 1,
    "method": 1,
    "travelpurposes": -1,
    "howmanyapplicantsareunder12": 0,
    "appointmentId": "undefined",
    "id": 0,
    "vac": { "id": 140 }
}
```
