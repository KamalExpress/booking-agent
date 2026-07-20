from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePortalAdapter(ABC):
    """
    Abstract interface for all Portal automation adapters.
    This allows the headless booker to switch seamlessly between GVC, BLS, VFS, etc.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        """
        Automate the login sequence for the portal.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def inject_applicant_data(self, applicant_data: Dict[str, Any], visa_center: str) -> bool:
        """
        Navigate to the booking page and inject applicant details.
        """
        pass

    @abstractmethod
    def pass_pre_otp_captcha(self) -> bool:
        """
        Detect and solve any secondary captcha required before requesting the OTP.
        """
        pass

    @abstractmethod
    def request_otp(self) -> bool:
        """
        Click the button to request the OTP to be sent via SMS/Email.
        """
        pass

    @abstractmethod
    def submit_otp_and_book(self, otp_code: str) -> bool:
        """
        Inject the received OTP code and finalize the booking.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Cleanup resources (close browser, clear cookies, etc.).
        """
        pass
