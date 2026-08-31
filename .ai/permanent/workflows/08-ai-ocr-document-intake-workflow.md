# AI OCR and MRZ Client Ingestion Workflow

## 1. Intent and Purpose
Provides an automated, high-speed intake pipeline for onboarding visa applicants into the SaaS Client Directory and Waitlist Queues using:
1. Fast client-side OCR (Tesseract.js in a Web Worker) for document photos/scans.
2. Built-in ICAO 9303 Machine Readable Zone (MRZ) deterministic parser.
3. Internal LLM endpoint (ai.alamiaconnect.com) powered by llama3.2_3b_instruct (or BitNet/Phi) for messy, forwarded text blurbs (WhatsApp/Telegram).

## 2. Invariants and Normalization Rules
All incoming data is normalized to match GVC / Portal requirements:
- **First Name and Surname:** Strictly uppercase, stripped of trailing < symbols.
- **Dates (DOB and Passport Expiry):** Strictly formatted as DD/MM/YYYY. Month names (JAN...DEC) and ICAO YYMMDD dates are dynamically resolved.
- **Gender:** Mapped to portal codes (1 = Male, 2 = Female).
- **Nationality:** Mapped to country IDs (197 = Pakistan).
- **Passport Number:** Alphanumeric uppercase string (e.g. EG9903901).
- **Phone Prefix and Number:** Stripped of leading 0 and separated from country code 92.

## 3. Architecture and Data Flow

`mermaid
sequenceDiagram
    autonumber
    actor Staff as Agency / SaaS Admin
    participant UI as Clients Directory (Browser)
    participant Tesseract as Tesseract.js Web Worker
    participant SaaS as Cloud SaaS Backend (ui.py)
    participant AI as Tiny-LLM Engine (ai.alamiaconnect.com)
    participant DB as PostgreSQL (Applicant and WaitlistQueue)

    Staff->>UI: Selects passport scan / photo OR pastes text
    alt Image Uploaded
        UI->>Tesseract: Runs client-side OCR
        Tesseract-->>UI: Returns raw text + MRZ lines
        UI->>UI: Fills raw text textarea with live progress
    end
    UI->>SaaS: POST /api/v1/ocr/parse-client (raw_text / file)
    alt MRZ lines present
        SaaS->>SaaS: Decodes ICAO 9303 MRZ directly
    else Complex unstructured text
        SaaS->>AI: POST /v1/chat/completions (model: llama3.2_3b_instruct)
        AI-->>SaaS: Returns JSON schema
    end
    SaaS-->>UI: Returns normalized applicant JSON
    UI->>UI: Pre-populates right-side review form
    Staff->>UI: Reviews / edits and clicks Save and Enqueue
    UI->>SaaS: POST /clients/save-ai-parsed (form_data + enqueue_now)
    SaaS->>DB: Inserts Applicant and WaitlistQueue records
    SaaS-->>UI: Redirects to /clients with success banner
`

## 4. Tradeoffs and Future Enhancements
- **Future Image Preprocessing:** Highly tilted or rotated phone photos may need automated canvas deskewing/rotation pre-processing before Tesseract OCR.
- **Orientation and Noise:** Low-light camera photos benefit from contrast stretching on canvas prior to OCR recognition.
