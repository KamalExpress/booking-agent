from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BasePortalAdapter(ABC):
    """
    Abstract base class for all portal automation adapters.
    This enforces a common interface so the core Execution Engine
    can dispatch tasks without knowing portal-specific implementation details.
    """
    
    def __init__(self, captcha_service=None, headless: bool = True, proxy_string: str = None):
        self.captcha_service = captcha_service
        self.headless = headless
        self.proxy_string = proxy_string
        self.cookie_file = None

    @abstractmethod
    def load_session(self) -> None:
        """Load session cookies if available."""
        pass

    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with the portal.
        Should raise WAFBlockedException or LoginFailedException on specific failures.
        """
        pass

    @abstractmethod
    def search_slots(self, session: Any, date_from: str, app_type: str, vac_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for available slots.
        Returns a list of dictionaries with slot details: [{"id": ..., "time": ..., "date": ...}]
        Should return None if network error occurs.
        """
        pass

    @abstractmethod
    def inject_applicant_data(self, applicant_data: dict, visa_center: str) -> None:
        """Fill out the applicant details in the portal's DOM."""
        pass

    @abstractmethod
    def pass_pre_otp_captcha(self) -> bool:
        """Solve any captchas required before requesting an OTP."""
        pass

    @abstractmethod
    def request_otp(self) -> None:
        """Trigger the OTP delivery from the portal."""
        pass

    @abstractmethod
    def submit_otp_and_book(self, otp_code: str) -> bool:
        """Submit the OTP and finalize the booking."""
        pass
