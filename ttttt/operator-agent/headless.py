import time
import logging
import sys
from slot_monitor import SlotMonitorEngine

import os
import queue
import threading

class SaaSStreamHandler(logging.Handler):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.log_queue = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.worker_thread.start()

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            pass

    def _flush_loop(self):
        while self.running:
            logs_to_send = []
            while not self.log_queue.empty() and len(logs_to_send) < 100:
                try:
                    logs_to_send.append(self.log_queue.get_nowait())
                except queue.Empty:
                    break
            
            if logs_to_send:
                try:
                    self.api_client.stream_logs(logs_to_send)
                except Exception:
                    pass
            time.sleep(3)
            
    def close(self):
        self.running = False
        super().close()

if __name__ == '__main__':
    base_url = os.getenv("SAAS_BASE_URL", "https://keagent.alamiaconnect.com")
    print(f"Starting Headless Worker Node connecting to {base_url}...")
    
    engine = SlotMonitorEngine(base_url)
    
    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)
    
    saas_handler = SaaSStreamHandler(engine.api)
    saas_handler.setFormatter(formatter)
    root_logger.addHandler(saas_handler)
    
    engine.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping worker...")
        engine.stop()
