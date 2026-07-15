import os
import time
import hmac
import hashlib
import requests
import logging
import threading
import platform
import sys

class SaaSClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.worker_id = None
        self.secret = None
        self.session = requests.Session()
        self._config_cache = None
        self._config_expires_at = 0
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
            
        labels = labels or {"system.location": location, "network.type": "residential"}
        
        # Attempt to gather system metrics
        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=True)
            ram = f"{round(psutil.virtual_memory().total / (1024**3), 2)}GB"
        except ImportError:
            cpu_cores = 2
            ram = "2GB"
            
        payload = {
            "hostname": hostname,
            "machine_id": "local",
            "os": platform.system(),
            "architecture": platform.machine(),
            "cpu_cores": cpu_cores,
            "ram": ram,
            "version": "1.0.0",
            "chrome_version": "120.0", # Mocked for now
            "playwright_version": "1.40.0", # Mocked for now
            "python_version": platform.python_version(),
            "max_concurrency": 1,
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

    def _request(self, method: str, path: str, json_data=None, headers=None):
        import json
        body = json.dumps(json_data).encode('utf-8') if json_data else b""
        req_headers = self._sign_request(method, path, body)
        if headers:
            req_headers.update(headers)
        if json_data:
            req_headers['Content-Type'] = 'application/json'
            
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                res = self.session.get(url, headers=req_headers)
            else:
                res = self.session.post(url, data=body, headers=req_headers)
            return res
        except Exception as e:
            logging.error(f"API request failed: {e}")
            return None

    def start_heartbeat(self):
        def _heartbeat_loop():
            while True:
                try:
                    cfg_ver = self._config_cache.get("version", 0) if self._config_cache else 0
                    res = self._request("POST", "/api/v1/worker/heartbeat", {
                        "cpu_percent": 0,
                        "ram_percent": 0,
                        "running_assignments": 0,
                        "public_ip": None, # Could resolve via icanhazip.com
                        "local_ip": "127.0.0.1",
                        "runtime_config_version": cfg_ver
                    })
                    if res and res.status_code == 200:
                        data = res.json()
                        if data.get("refresh_runtime_config"):
                            logging.info("SaaS requested runtime config refresh")
                            self.get_runtime_config(force=True)
                    else:
                        logging.warning("Heartbeat failed")
                except Exception as e:
                    logging.error(f"Heartbeat error: {e}")
                time.sleep(30)
                
        t = threading.Thread(target=_heartbeat_loop, daemon=True)
        t.start()
        
    def get_runtime_config(self, force=False):
        now = time.time()
        
        # Return cached config if TTL hasn't expired and not forced
        if not force and self._config_cache and now < self._config_expires_at:
            return self._config_cache
            
        res = self._request("GET", "/api/v1/worker/runtime-config")
        if not res:
            return self._config_cache # Fallback to stale cache if network fails
            
        if res.status_code == 200:
            config = res.json()
            self._config_cache = config
            self._config_expires_at = now + config.get("ttl", 1800)
            return config
            
        return self._config_cache
        
    def get_next_lease(self):
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
        self._request("POST", f"/api/v1/worker/logs", {
            "assignment_id": assignment_id,
            "severity": severity,
            "event_type": event_type,
            "payload": payload
        })
        
    def complete_assignment(self, assignment_id: int):
        self._request("POST", f"/api/v1/worker/assignments/{assignment_id}/complete")
