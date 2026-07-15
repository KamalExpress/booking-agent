import time
import logging
import sys
from slot_monitor import SlotMonitorEngine

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

import os

if __name__ == '__main__':
    base_url = os.getenv("SAAS_BASE_URL", "https://keagent.alamiaconnect.com")
    print(f"Starting Headless Worker Node connecting to {base_url}...")
    engine = SlotMonitorEngine(base_url)
    engine.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping worker...")
        engine.stop()
