import os
import time
import requests
import logging
from core.captcha_service import CaptchaService

class MockCaptchaService(CaptchaService):
    """
    A strictly local mock captcha solver used for testing the ecosystem
    without burning real API credits or failing on 402 Quota errors.
    """
    def __init__(self):
        pass

    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        logging.info(f"Mocking CAPTCHA solve for sitekey {sitekey} on {url}...")
        time.sleep(2)  # Simulate network delay
        return "LOCAL_DUMMY_TOKEN"
