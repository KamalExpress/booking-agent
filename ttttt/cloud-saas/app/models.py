import os
import enum
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, backref

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
    webhook_url = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    has_ai_copilot = Column(Boolean, default=True)
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
    preferences = Column(JSONB, default=dict)
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

class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parent_id = Column(Integer, ForeignKey("inbox_messages.id", ondelete="CASCADE"), nullable=True)
    
    is_system_alert = Column(Boolean, default=False)
    severity = Column(String, default="info") # info, warning, error, success
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant")
    sender = relationship("User")
    replies = relationship("InboxMessage", backref=backref('parent', remote_side=[id]), cascade="all, delete-orphan")

class Applicant(Base):
    __tablename__ = "applicants"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    surname = Column(String, nullable=False)
    firstname = Column(String, nullable=False)
    dateofbirth = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    passportnumber = Column(String, nullable=False)
    passport_expiry = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone_prefix = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    provider_metadata = Column(JSONB, default=dict) # e.g., GWF number
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant")
    waitlist_entries = relationship("WaitlistQueue", back_populates="applicant", cascade="all, delete-orphan")

class WaitlistQueue(Base):
    __tablename__ = "waitlist_queue"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    applicant_id = Column(Integer, ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String, default="GVC")
    visa_center = Column(String, nullable=False)
    appointment_type = Column(String, default="0")
    status = Column(String, default="PENDING") # PENDING, BOOKED, CANCELLED
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant")
    applicant = relationship("Applicant", back_populates="waitlist_entries")

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
    can_scrape = Column(Boolean, default=True)
    can_book = Column(Boolean, default=False)
    
    # State
    last_heartbeat = Column(DateTime, nullable=True)
    status = Column(String, default="Offline") # Online, Offline, Error
    scheduling_state = Column(String, default="Accepting Jobs") # Accepting Jobs, Stop Accepting Jobs, Draining, Disabled, Maintenance
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archived_by = relationship("User", foreign_keys=[archived_by_id])
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
        return age <= self.WORKER_TIMEOUT_SECONDS and self.status == "Online"

    @property
    def agent_type_label(self):
        if self.can_book and not self.can_scrape:
            return "Booking Agent"
        elif self.can_scrape and not self.can_book:
            return "Slot Agent"
        elif self.can_scrape and self.can_book:
            return "Dual Agent"
        else:
            return "Worker"

    @property
    def human_heartbeat_age(self):
        age_seconds = self.heartbeat_age
        if age_seconds is None:
            return "Never"
        sec = int(max(0, age_seconds))
        if sec < 60:
            return f"{sec}s ago"
        mins = sec // 60
        if mins < 60:
            rem_sec = sec % 60
            return f"{mins}m {rem_sec}s ago" if rem_sec > 0 else f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            rem_mins = mins % 60
            return f"{hours}h {rem_mins}m ago" if rem_mins > 0 else f"{hours}h ago"
        days = hours // 24
        rem_hours = hours % 24
        if days < 30:
            return f"{days}d {rem_hours}h ago" if rem_hours > 0 else f"{days}d ago"
        months = days // 30
        rem_days = days % 30
        return f"{months}mo {rem_days}d ago"

class PortalAccount(Base):
    __tablename__ = "portal_accounts"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    account_name = Column(String, nullable=True) # e.g., "Jameel", "Tayyab"
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    provider = Column(String, default="GVC")
    supports_scraping = Column(Boolean, default=True)
    supports_booking = Column(Boolean, default=False)
    
    status = Column(String, default="READY") # READY, LEASED, COOLDOWN, DISABLED
    health_score = Column(Integer, default=100)
    failure_count = Column(Integer, default=0)
    cooldown_until = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)
    last_failure = Column(DateTime, nullable=True)
    
    bookings_in_window = Column(Integer, default=0)
    booking_window_start = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archived_by = relationship("User", foreign_keys=[archived_by_id])
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def display_name(self):
        if self.account_name and self.account_name.strip():
            return self.account_name.strip()
        if self.username and "@" in self.username:
            return self.username.split("@")[0]
        return self.username or f"Account #{self.id}"

class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    host = Column(String, nullable=False)
    port = Column(String, nullable=False)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    supports_scraping = Column(Boolean, default=True)
    supports_booking = Column(Boolean, default=False)
    
    status = Column(String, default="READY") # READY, LEASED, COOLDOWN, DISABLED
    health_score = Column(Integer, default=100)
    cooldown_until = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def proxy_string(self) -> str:
        h = self.host.strip() if self.host else ""
        p = self.port.strip() if isinstance(self.port, str) else self.port
        if self.username and self.password:
            u = self.username.strip()
            pw = self.password.strip().replace("\r", "").replace("\n", "")
            return f"http://{u}:{pw}@{h}:{p}"
        return f"http://{h}:{p}"

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, default="GVC")
    visa_center = Column(String, default="138")
    date_from = Column(String, nullable=False)
    date_to = Column(String, nullable=False)
    polling_interval = Column(Integer, default=300)
    priority = Column(Integer, default=0)
    status = Column(String, default="Active")
    required_labels = Column(JSONB, default=dict)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BookingTask(Base):
    __tablename__ = "booking_tasks"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id", ondelete="SET NULL"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    provider = Column(String, default="GVC")
    visa_center = Column(String, nullable=False)
    target_date = Column(String, nullable=False)
    target_time = Column(String, nullable=False)
    slot_payload = Column(JSONB, nullable=True)
    otp_code = Column(String, nullable=True)
    
    priority = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    
    status = Column(String, default="PENDING") # PENDING, CLAIMED, SUCCESS, FAILED, EXPIRED
    active_status = Column(Boolean, default=True) # Used for unique constraint
    failure_reason = Column(String, nullable=True)
    failure_details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'visa_center', 'target_date', 'target_time', 'active_status', name='uq_booking_task'),
    )

class SchedulerDecision(Base):
    __tablename__ = "scheduler_decisions"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=True)
    selected_assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    selected_booking_task_id = Column(Integer, ForeignKey("booking_tasks.id"), nullable=True)
    selected_account_id = Column(Integer, ForeignKey("portal_accounts.id"), nullable=True)
    selected_proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    
    decision_type = Column(String, nullable=False) # SUCCESS, NO_READY_ACCOUNT, etc.
    decision_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Lease(Base):
    __tablename__ = "leases"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    booking_task_id = Column(Integer, ForeignKey("booking_tasks.id"), nullable=True)
    portal_account_id = Column(Integer, ForeignKey("portal_accounts.id"), nullable=True)
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    
    lease_version = Column(Integer, default=1)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_heartbeat = Column(DateTime, nullable=True)
    status = Column(String, default="Pending") # Pending, Leased, Running, Completed, Expired, Cancelled, Failed, Abandoned
    created_at = Column(DateTime, default=datetime.utcnow)

class LeaseArchive(Base):
    __tablename__ = "lease_archives"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, ForeignKey("worker_nodes.worker_id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    booking_task_id = Column(Integer, ForeignKey("booking_tasks.id"), nullable=True)
    portal_account_id = Column(Integer, ForeignKey("portal_accounts.id"), nullable=True)
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    
    expires_at = Column(DateTime, nullable=False)
    last_heartbeat = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    archived_at = Column(DateTime, default=datetime.utcnow)

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

class SlotAvailability(Base):
    __tablename__ = "slot_availability"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    visa_center = Column(String, nullable=False)
    date = Column(String, nullable=False)
    slots_data = Column(JSONB, nullable=False)
    found_by = Column(String, nullable=True) # The worker_id that found the slot
    status = Column(String, default="AVAILABLE", nullable=False) # AVAILABLE, VERIFYING, UNAVAILABLE
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archived_by = relationship("User", foreign_keys=[archived_by_id])
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

class OTPChallenge(Base):
    __tablename__ = "otp_challenges"
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(String, unique=True, index=True, nullable=False) # UUID
    booking_task_id = Column(Integer, ForeignKey("booking_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    
    applicant_name = Column(String, nullable=True)
    visa_center = Column(String, nullable=True)
    appointment_type = Column(String, nullable=True)
    
    status = Column(String, default="PENDING", index=True) # PENDING, SUBMITTED, CONSUMED, EXPIRED, CANCELLED
    otp_code = Column(String, nullable=True) # Ephemeral: wiped upon CONSUMED
    
    expires_in_seconds = Column(Integer, default=300)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)
    submitted_by = Column(String, nullable=True) # User email or 'HUMAN_ENTRY'
    attempt_count = Column(Integer, default=0)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
