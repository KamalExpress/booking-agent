import os
import enum
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/booking_saas")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Enums ---
class RoleEnum(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    STAFF = "STAFF"

# --- Models ---
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.STAFF, nullable=False)
    is_active = Column(Boolean, default=True)
    can_solve_captcha = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="users")
    logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    action = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="logs")
    tenant = relationship("Tenant", back_populates="logs")

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    endpoint = Column(String, unique=True, nullable=False)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    
    # Metadata
    ip_address = Column(String, nullable=True)
    location = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    os_name = Column(String, nullable=True)
    device_name = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="push_subscriptions")

class MonitorConfig(Base):
    """Global configuration managed only by Super Admins."""
    __tablename__ = "monitor_configs"
    id = Column(Integer, primary_key=True, index=True)
    date_from = Column(String, default="01/09/2026")
    date_to = Column(String, default="15/09/2026")
    holidays = Column(String, default="SAT,SUN")
    interval_minutes = Column(Integer, default=5)
    app_type = Column(String, default="26")
    vac_id = Column(String, default="138")
    is_active = Column(Boolean, default=False) # Switch to easily pause entire global scraping
    is_demo = Column(Boolean, default=False)

class WorkerNode(Base):
    __tablename__ = "worker_nodes"
    worker_id = Column(String, primary_key=True, index=True)
    secret_hash = Column(String, nullable=False)
    labels = Column(JSONB, default=dict) # e.g., {"system.os": "windows"}
    version = Column(String, nullable=True)
    git_commit = Column(String, nullable=True)
    
    # Network
    observed_ip = Column(String, nullable=True)
    public_ip = Column(String, nullable=True)
    local_ip = Column(String, nullable=True)
    
    # Capabilities
    os = Column(String, nullable=True)
    architecture = Column(String, nullable=True)
    chrome_version = Column(String, nullable=True)
    playwright_version = Column(String, nullable=True)
    python_version = Column(String, nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    ram = Column(String, nullable=True)
    max_concurrency = Column(Integer, default=1)
    current_concurrency = Column(Integer, default=0)
    
    # State
    last_heartbeat = Column(DateTime, nullable=True)
    status = Column(String, default="Offline") # Online, Offline, Error
    scheduling_state = Column(String, default="Accepting Jobs") # Accepting Jobs, Stop Accepting Jobs, Draining, Disabled, Maintenance
    created_at = Column(DateTime, default=datetime.utcnow)

    HEARTBEAT_INTERVAL_SECONDS = 30
    WORKER_TIMEOUT_SECONDS = 90

    @property
    def heartbeat_age(self):
        if not self.last_heartbeat:
            return None
        # Use timezone.utc for timezone-aware calculations instead of utcnow()
        now = datetime.now(timezone.utc).replace(tzinfo=None) # Keep naive comparison if DB is naive
        return (now - self.last_heartbeat).total_seconds()

    @property
    def is_online(self):
        age = self.heartbeat_age
        if age is None:
            return False
        return age < self.WORKER_TIMEOUT_SECONDS

class ScraperAccount(Base):
    __tablename__ = "scraper_accounts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    proxy_string = Column(String, nullable=True)
    proxy_mode = Column(String, default="LEGACY") # LEGACY, POOL
    preferred_worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=True)
    status = Column(String, default="Idle") # Idle, Leased, Banned
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    scraper_account_id = Column(Integer, ForeignKey("scraper_accounts.id"), nullable=False)
    visa_center = Column(String, default="138")
    date_from = Column(String, nullable=False)
    date_to = Column(String, nullable=False)
    polling_interval = Column(Integer, default=300)
    priority = Column(Integer, default=0)
    status = Column(String, default="Active")
    required_labels = Column(JSONB, default=dict)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Lease(Base):
    __tablename__ = "leases"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_heartbeat = Column(DateTime, nullable=True)
    status = Column(String, default="Pending") # Pending, Leased, Running, Completed, Expired, Cancelled, Failed, Abandoned
    created_at = Column(DateTime, default=datetime.utcnow)

class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=True)
    worker_id = Column(String, nullable=True)
    assignment_id = Column(Integer, nullable=True)
    severity = Column(String, default="info") # info, warning, error
    event_type = Column(String, nullable=False) # LOGIN_SUCCESS, RATE_LIMIT, etc
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkerLog(Base):
    """Stores HAR-like network intercepts from headless workers for WAF debugging."""
    __tablename__ = "worker_logs"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    payload = Column(JSONB, nullable=False) # The JSON dump of network requests/responses
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkerVersion(Base):
    __tablename__ = "worker_versions"
    version = Column(String, primary_key=True, index=True)
    is_supported = Column(Boolean, default=True)
    deprecated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True) # Used for plaintext settings
    encrypted_value = Column(String, nullable=True) # Used for secrets
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, nullable=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
