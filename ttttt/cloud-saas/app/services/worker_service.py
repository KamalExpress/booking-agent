from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import secrets
from typing import Tuple, Dict, Any, Optional
from fastapi import Depends

from models import WorkerNode, WorkerVersion, SystemSetting, EventLog, get_db
from secrets_manager import secrets_manager

class WorkerService:
    def __init__(self, db: Session):
        self.db = db
        
    def register_worker(self, req, client_host: str) -> Tuple[str, str]:
        # Enforce minimum version
        wv = self.db.query(WorkerVersion).filter(WorkerVersion.version == req.version).first()
        if wv and not wv.is_supported:
            raise ValueError("Worker version is no longer supported.")

        worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        secret = secrets.token_hex(32)
        
        worker = WorkerNode(
            worker_id=worker_id,
            secret_hash=secret,
            labels=req.labels,
            version=req.version,
            observed_ip=client_host,
            os=req.os,
            architecture=req.architecture,
            cpu_cores=req.cpu_cores,
            ram=req.ram,
            chrome_version=req.chrome_version,
            playwright_version=req.playwright_version,
            python_version=req.python_version,
            max_concurrency=req.max_concurrency,
            status="Online",
            scheduling_state="Accepting Jobs",
            last_heartbeat=datetime.utcnow()
        )
        self.db.add(worker)
        
        log = EventLog(
            source="worker_service",
            worker_id=worker_id,
            severity="info",
            event_type="WORKER_REGISTERED",
            payload={"version": req.version, "os": req.os}
        )
        self.db.add(log)
        
        self.db.commit()
        return worker_id, secret

    def process_heartbeat(self, worker: WorkerNode, req, client_host: str) -> bool:
        worker.last_heartbeat = datetime.utcnow()
        worker.public_ip = req.public_ip
        worker.local_ip = req.local_ip
        worker.observed_ip = client_host if client_host else worker.observed_ip
        worker.status = "Online"
        worker.current_concurrency = req.running_assignments
        
        # Check if runtime config needs refresh
        saas_version_setting = self.db.query(SystemSetting).filter(SystemSetting.key == "runtime.config.version").first()
        saas_version = int(saas_version_setting.value) if saas_version_setting and saas_version_setting.value else 1
        refresh = req.runtime_config_version < saas_version
            
        self.db.commit()
        return refresh

    def mark_worker_offline(self, worker_id: str):
        worker = self.db.query(WorkerNode).filter(WorkerNode.worker_id == worker_id).first()
        if worker:
            worker.status = "Offline"
            log = EventLog(
                source="worker_service",
                worker_id=worker_id,
                severity="info",
                event_type="WORKER_OFFLINE",
                payload={"reason": "graceful_shutdown"}
            )
            self.db.add(log)
            self.db.commit()

    def get_runtime_config(self) -> Dict[str, Any]:
        saas_version_setting = self.db.query(SystemSetting).filter(SystemSetting.key == "runtime.config.version").first()
        saas_version = int(saas_version_setting.value) if saas_version_setting and saas_version_setting.value else 1
        
        captcha_provider = self.db.query(SystemSetting).filter(SystemSetting.key == "captcha.provider").first()
        captcha_api_key_setting = self.db.query(SystemSetting).filter(SystemSetting.key == "captcha.api_key").first()
        
        decrypted_api_key = ""
        if captcha_api_key_setting:
            if captcha_api_key_setting.encrypted_value:
                decrypted_api_key = secrets_manager.decrypt(captcha_api_key_setting.encrypted_value)
            elif captcha_api_key_setting.value:
                decrypted_api_key = captcha_api_key_setting.value
                
        min_slot_delay = self.db.query(SystemSetting).filter(SystemSetting.key == "global.min_slot_delay").first()
        max_slot_delay = self.db.query(SystemSetting).filter(SystemSetting.key == "global.max_slot_delay").first()
        
        return {
            "version": saas_version,
            "ttl": 1800,
            "captcha": {
                "provider": captcha_provider.value if captcha_provider else "capsolver",
                "api_key": decrypted_api_key
            },
            "proxy": {},
            "browser": {
                "headless": True,
                "launch_timeout": 60000,
                "default_timeout": 30000
            },
            "polling": {
                "interval_seconds": 300
            },
            "behavior": {
                "min_slot_delay": float(min_slot_delay.value) if min_slot_delay else 4.0,
                "max_slot_delay": float(max_slot_delay.value) if max_slot_delay else 8.0
            },
            "feature_flags": {
                "enable_telemetry": True
            },
            "limits": {
                "max_retries": 3
            }
        }

def get_worker_service(db: Session = Depends(get_db)) -> WorkerService:
    return WorkerService(db)
