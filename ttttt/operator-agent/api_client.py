import os
import time
import hmac
import hashlib
import requests
import logging
import threading

class SaaSClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.worker_id = None
        self.secret = None
        self.session = requests.Session()
        self.load_credentials()

    def load_credentials(self):
        try:
            if os.path.exists("worker_creds.txt"):
                with open("worker_creds.txt", "r") as f:
                    self.worker_id, self.secret = f.read().strip().split(':')
                logging.info(f"Loaded existing worker credentials: {self.worker_id}")
        except Exception as e:
            logging.error(f"Could not load worker credentials: {e}")

    def save_credentials(self):
        with open("worker_creds.txt", "w") as f:
            f.write(f"{self.worker_id}:{self.secret}")

    def register(self, hostname="worker", location="unknown", labels=None):
        if self.worker_id and self.secret:
            return True
            
        labels = labels or ["desktop"]
        payload = {
            "hostname": hostname,
            "machine_id": "local",
            "os": os.name,
            "cpu": "unknown",
            "ram": "unknown",
            "version": "1.0",
            "location": location,
            "labels": labels
        }
        try:
            res = self.session.post(f"{self.base_url}/api/v1/worker/register", json=payload)
            res.raise_for_status()
            data = res.json()
            self.worker_id = data['worker_id']
            self.secret = data['secret']
            self.save_credentials()
            logging.info(f"Registered new worker: {self.worker_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to register worker: {e}")
            return False

    def _sign_request(self, method: str, path: str, body: bytes):
        ts = str(int(time.time()))
        payload = ts.encode('utf-8') + method.encode('utf-8') + path.encode('utf-8') + body
        signature = hmac.new(
            self.secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return {
            "x-worker-id": self.worker_id,
            "x-timestamp": ts,
            "x-signature": signature
        }

    def _request(self, method: str, path: str, json_data=None):
        import json
        body = json.dumps(json_data).encode('utf-8') if json_data else b""
        headers = self._sign_request(method, path, body)
        if json_data:
            headers['Content-Type'] = 'application/json'
            
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                res = self.session.get(url, headers=headers)
            else:
                res = self.session.post(url, data=body, headers=headers)
            return res
        except Exception as e:
            logging.error(f"API request failed: {e}")
            return None

    def start_heartbeat(self):
        def _heartbeat_loop():
            while True:
                try:
                    res = self._request("POST", "/api/v1/worker/heartbeat", {
                        "cpu_percent": 0,
                        "ram_percent": 0,
                        "running_assignments": 0
                    })
                    if res and res.status_code == 200:
                        logging.debug("Heartbeat successful")
                    else:
                        logging.warning("Heartbeat failed")
                except Exception as e:
                    logging.error(f"Heartbeat error: {e}")
                time.sleep(30)
                
        t = threading.Thread(target=_heartbeat_loop, daemon=True)
        t.start()
        
    def get_next_assignment(self):
        res = self._request("GET", "/api/v1/worker/assignments/next")
        if not res:
            return None, 30
            
        if res.status_code == 204:
            retry = int(res.headers.get("Retry-After", 30))
            return None, retry
            
        if res.status_code == 200:
            return res.json(), 0
            
        return None, 30

    def log_event(self, assignment_id: int, event_type: str, severity: str, payload: dict):
        self._request("POST", f"/api/v1/worker/assignments/{assignment_id}/event", {
            "severity": severity,
            "event_type": event_type,
            "payload": payload
        })
