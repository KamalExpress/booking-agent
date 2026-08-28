import os
import re
import json
import logging
import requests
from typing import Optional, Dict, Any

class AiOcrService:
    """
    Intelligent document extraction service utilizing the internal AI endpoint (BitNet / Phi / Tiny LLMs)
    at ai.alamiaconnect.com with fallback heuristic normalization.
    """
    
    DEFAULT_API_URL = "https://ai.alamiaconnect.com"
    DEFAULT_MODEL = "bitnet-b1.58-large"

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        raw_url = (api_url or os.getenv("BITNET_SERVER_URL") or os.getenv("BITNET_AI_URL") or self.DEFAULT_API_URL).strip()
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = f"https://{raw_url}"
        self.api_url = raw_url.rstrip("/")
        self.api_key = api_key or os.getenv("BITNET_API_KEY") or ""
        self.model = model or os.getenv("BITNET_MODEL_NAME") or self.DEFAULT_MODEL

    def extract_from_document(self, raw_text: str = "", file_bytes: bytes = None, filename: str = "", mime_type: str = "") -> Dict[str, Any]:
        """
        Parses document (image, PDF, or raw text) using Vision / Multimodal or Text LLM.
        """
        if file_bytes and len(file_bytes) > 0:
            is_image = mime_type.startswith("image/") or any(filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"])
            
            # If it's an image and AI endpoint is configured, call Vision AI completion
            if is_image:
                import base64
                b64_img = base64.b64encode(file_bytes).decode("utf-8")
                actual_mime = mime_type or ("image/png" if filename.lower().endswith(".png") else "image/jpeg")
                
                if self.api_key:
                    try:
                        ai_result = self._call_ai_vision_completion(b64_img, actual_mime)
                        if ai_result and not ai_result.get("error"):
                            return self._normalize_extracted_data(ai_result, f"[Image Document: {filename}]")
                    except Exception as e:
                        logging.error(f"[AiOcrService] Vision AI API failed: {e}")
                        
            # If PDF or text file, attempt text decode
            if not raw_text:
                try:
                    raw_text = file_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    pass

        if not raw_text or not raw_text.strip():
            # If we reached here without text or vision result
            if file_bytes and len(file_bytes) > 0:
                return {"error": "Could not extract text from document. Please ensure the AI endpoint supports Vision or paste the details."}
            return {"error": "Empty document provided"}

        # Text LLM fallback
        if self.api_key:
            try:
                ai_result = self._call_ai_completion(raw_text)
                if ai_result and not ai_result.get("error"):
                    return self._normalize_extracted_data(ai_result, raw_text)
            except Exception as e:
                logging.error(f"[AiOcrService] AI API call failed: {e}. Falling back to heuristic extraction.")

        return self._heuristic_extract(raw_text)

    def extract_from_text(self, raw_text: str) -> Dict[str, Any]:
        return self.extract_from_document(raw_text=raw_text)

    def _call_ai_vision_completion(self, b64_img: str, mime_type: str) -> Dict[str, Any]:
        """
        Invokes multimodal / vision completion using OpenAI-compatible payload.
        """
        endpoint = f"{self.api_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        system_prompt = (
            "You are a specialized visa applicant passport and document OCR reader. "
            "Extract the following fields from the passport or ID document image into a valid JSON object:\n"
            "- firstname: string (Given names in uppercase, e.g. 'MUHAMMAD USMAN')\n"
            "- surname: string (Surname in uppercase, e.g. 'KHAN')\n"
            "- dateofbirth: string strictly in DD/MM/YYYY format\n"
            "- gender: string ('1' for Male, '2' for Female)\n"
            "- nationality: string ('197' for Pakistan, or standard country ID)\n"
            "- passportnumber: string uppercase alphanumeric (e.g. 'PK1234567')\n"
            "- passport_expiry: string strictly in DD/MM/YYYY format\n"
            "- email: string or empty string\n"
            "- phone_prefix: string without plus sign (e.g. '92')\n"
            "- phone_number: string without leading zero (e.g. '3345112969')\n\n"
            "Return ONLY valid raw JSON without markdown formatting or code blocks."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all applicant details from this passport document into strict JSON format."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 512
        }

        response = requests.post(endpoint, json=payload, headers=headers, timeout=45)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^```\s*", "", content)
            content = re.sub(r"```$", "", content)
            
            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return {"error": "Invalid JSON returned by Vision AI"}
        else:
            logging.error(f"[AiOcrService] Vision HTTP {response.status_code}: {response.text}")
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}

    def _call_ai_completion(self, document_text: str) -> Dict[str, Any]:
        """
        Invokes text /v1/chat/completions on the internal AI server.
        """
        endpoint = f"{self.api_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        system_prompt = (
            "You are a specialized visa applicant information extraction system. "
            "Extract the following fields from the given text into a valid JSON object:\n"
            "- firstname: string (e.g. 'MUHAMMAD')\n"
            "- surname: string (e.g. 'USMAN')\n"
            "- dateofbirth: string strictly in DD/MM/YYYY format (e.g. '15/08/1994')\n"
            "- gender: string ('1' for Male, '2' for Female)\n"
            "- nationality: string ('197' for Pakistan, or standard country ID)\n"
            "- passportnumber: string uppercase alphanumeric (e.g. 'PK1234567')\n"
            "- passport_expiry: string strictly in DD/MM/YYYY format\n"
            "- email: string or empty string\n"
            "- phone_prefix: string without plus sign (e.g. '92')\n"
            "- phone_number: string without leading zero (e.g. '3345112969')\n\n"
            "Return ONLY valid raw JSON without markdown formatting or code blocks."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Text:\n{document_text}"}
            ],
            "temperature": 0.1,
            "max_tokens": 512
        }

        response = requests.post(endpoint, json=payload, headers=headers, timeout=25)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^```\s*", "", content)
            content = re.sub(r"```$", "", content)
            
            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return {"error": "Invalid JSON returned by AI"}
        else:
            logging.error(f"[AiOcrService] HTTP {response.status_code}: {response.text}")
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}

    def _normalize_extracted_data(self, data: Dict[str, Any], original_text: str = "") -> Dict[str, Any]:
        """
        Normalizes and validates fields to strictly conform to GVC requirements.
        """
        # Ensure uppercase for names & passport
        firstname = str(data.get("firstname", "")).strip().upper()
        surname = str(data.get("surname", "")).strip().upper()
        passportnumber = str(data.get("passportnumber", "")).strip().upper().replace(" ", "")
        
        # Normalize Dates to DD/MM/YYYY
        dob = self._clean_date(str(data.get("dateofbirth", "")))
        expiry = self._clean_date(str(data.get("passport_expiry", "")))
        
        # Gender normalization (1 = Male, 2 = Female)
        gender_raw = str(data.get("gender", "")).strip().lower()
        if gender_raw in ["1", "m", "male", "man"]:
            gender = "1"
        elif gender_raw in ["2", "f", "female", "woman"]:
            gender = "2"
        else:
            gender = "1"
            
        # Nationality (Default 197 Pakistan)
        nat_raw = str(data.get("nationality", "197")).strip()
        nationality = "197" if "pak" in nat_raw.lower() or nat_raw in ["197", "pk", "pakistan"] else nat_raw
        
        # Phone normalization
        phone_raw = str(data.get("phone_number", "")).strip().replace("-", "").replace(" ", "").replace("+", "")
        prefix_raw = str(data.get("phone_prefix", "92")).strip().replace("+", "")
        
        if phone_raw.startswith("92") and len(phone_raw) >= 11:
            prefix_raw = "92"
            phone_raw = phone_raw[2:]
        phone_clean = phone_raw.lstrip("0")
        
        email = str(data.get("email", "")).strip().lower()
        
        # Generate formatted summary blurb if original_text is short/image tag
        blurb = original_text
        if not blurb or blurb.startswith("[Image Document"):
            blurb = (
                f"Applicant Name: {firstname} {surname}\n"
                f"Passport No: {passportnumber}\n"
                f"DOB: {dob}\n"
                f"Passport Expiry: {expiry}\n"
                f"Gender: {'Male' if gender == '1' else 'Female'}\n"
                f"Mobile: +{prefix_raw} {phone_clean}\n"
                f"Email: {email if email else 'N/A'}"
            )
        
        return {
            "firstname": firstname,
            "surname": surname,
            "dateofbirth": dob,
            "gender": gender,
            "nationality": nationality,
            "passportnumber": passportnumber,
            "passport_expiry": expiry,
            "phone_prefix": prefix_raw,
            "phone_number": phone_clean,
            "email": email,
            "raw_text_snippet": blurb
        }

    def _clean_date(self, date_str: str) -> str:
        """Converts heterogeneous date representations into standard DD/MM/YYYY."""
        if not date_str:
            return ""
        date_str = date_str.strip().replace("-", "/").replace(".", "/")
        
        # Check DD/MM/YYYY
        if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
            return date_str
            
        # Check YYYY/MM/DD
        match_ymd = re.match(r'^(\d{4})/(\d{2})/(\d{2})$', date_str)
        if match_ymd:
            y, m, d = match_ymd.groups()
            return f"{d}/{m}/{y}"
            
        # Check D/M/YYYY
        match_short = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
        if match_short:
            d, m, y = match_short.groups()
            return f"{int(d):02d}/{int(m):02d}/{y}"
            
        return date_str

    def _heuristic_extract(self, text: str) -> Dict[str, Any]:
        """
        Pure regex/deterministic extractor for MRZ passports and standard intake sheets.
        """
        data = {
            "firstname": "",
            "surname": "",
            "dateofbirth": "",
            "gender": "1",
            "nationality": "197",
            "passportnumber": "",
            "passport_expiry": "",
            "phone_prefix": "92",
            "phone_number": "",
            "email": ""
        }
        
        # 1. Passport MRZ parsing if available (P<PAK...)
        mrz_match = re.search(r'P<([A-Z]{3})([A-Z<]+)\n([A-Z0-9<]{9})', text)
        if mrz_match:
            country = mrz_match.group(1)
            name_parts = mrz_match.group(2).split("<<")
            if len(name_parts) >= 2:
                data["surname"] = name_parts[0].replace("<", " ").strip()
                data["firstname"] = name_parts[1].replace("<", " ").strip()
            data["passportnumber"] = mrz_match.group(3).replace("<", "").strip()
            if country == "PAK":
                data["nationality"] = "197"
                
        # 2. Passport Number Regex
        if not data["passportnumber"]:
            pp_match = re.search(r'(?:passport|pp|doc)[\s#:]*([A-Z]{1,2}[0-9]{7,8})', text, re.IGNORECASE)
            if pp_match:
                data["passportnumber"] = pp_match.group(1).upper()
            else:
                # Standalone passport format e.g. FS9910272, PK1234567
                pp_standalone = re.search(r'\b([A-Z]{2}[0-9]{7})\b', text)
                if pp_standalone:
                    data["passportnumber"] = pp_standalone.group(1)
                    
        # 3. Name Regex (Check line-by-line first)
        if not data["firstname"]:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for line in lines:
                name_match = re.search(r'^(?:Applicant\s+Name|Name|Full\s+Name|Client\s+Name)[\s:]+([A-Za-z\s]+)$', line, re.IGNORECASE)
                if name_match:
                    full_name = name_match.group(1).strip().split()
                    if len(full_name) == 1:
                        data["firstname"] = full_name[0].upper()
                    elif len(full_name) >= 2:
                        data["firstname"] = " ".join(full_name[:-1]).upper()
                        data["surname"] = full_name[-1].upper()
                    break

        # 4. DOB & Expiry Regex
        dob_match = re.search(r'(?:dob|birth|date of birth)[\s:]*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})', text, re.IGNORECASE)
        if dob_match:
            data["dateofbirth"] = self._clean_date(dob_match.group(1))
            
        exp_match = re.search(r'(?:expiry|valid until|exp)[\s:]*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})', text, re.IGNORECASE)
        if exp_match:
            data["passport_expiry"] = self._clean_date(exp_match.group(1))
            
        # 5. Phone Regex
        for line in text.split("\n"):
            phone_match = re.search(r'(?:phone|mobile|tel|cell|number)[\s:#]*([+0-9\s-]{10,25})', line, re.IGNORECASE)
            if phone_match:
                raw_p = phone_match.group(1).strip()
                # Check if it has digits
                if re.search(r'\d{7,}', raw_p.replace(" ", "")):
                    data["phone_number"] = raw_p
                    break
        if not data["phone_number"]:
            raw_phone = re.search(r'(\+?92[\s-]?3[0-9]{2}[\s-]?[0-9]{7}|03[0-9]{9})', text)
            if raw_phone:
                data["phone_number"] = raw_phone.group(1)
                
        # 6. Email Regex
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            data["email"] = email_match.group(0).lower()
            
        return self._normalize_extracted_data(data, text)
