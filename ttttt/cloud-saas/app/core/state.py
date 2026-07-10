import threading
import collections
import logging

class MemoryLogHandler(logging.Handler):
    def __init__(self, max_len=5000):
        super().__init__()
        self.log_queue = collections.deque(maxlen=max_len)
        
    def emit(self, record):
        log_entry = self.format(record)
        self.log_queue.append(log_entry)

# Global instances
cloud_log_handler = MemoryLogHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
cloud_log_handler.setFormatter(formatter)

class PendingCaptchaState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_pending = False
        self.sitekey = ""
        self.url = ""
        self.solved_token = None
        self.event = threading.Event()
        
    def request_captcha(self, sitekey: str, url: str):
        with self.lock:
            self.is_pending = True
            self.sitekey = sitekey
            self.url = url
            self.solved_token = None
            self.event.clear()
            
    def submit_token(self, token: str):
        with self.lock:
            self.solved_token = token
            self.is_pending = False
            self.event.set()

global_captcha_state = PendingCaptchaState()
